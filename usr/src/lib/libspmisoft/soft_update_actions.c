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



#include "spmisoft_lib.h"
#include "soft_locale.h"
#include "instzones_lib.h"

#include <signal.h>
#include <fcntl.h>
#include <dirent.h>
#include <netdb.h>
#include <string.h>
#include <stdlib.h>
#include <libintl.h>
#include <libcontract.h>
#include <sys/wait.h>
#include <unistd.h>
#include <sys/stropts.h>
#include <sys/ctfs.h>
#include <sys/contract/process.h>

struct client {
	struct client	*next_client;
	char		client_name[MAXHOSTNAMELEN];
	char		*client_root;
};

static int diskless_install;

/* Public Functions */
int
set_action_code_mode(ActionCodeMode);

/* Public Statics */
char		*swdebug_pkg_name = "SUNWnosuchpkg";
SW_diffrev	*g_sw_diffrev = NULL;

/* Local Statics and Constats */

static char	*template_dir = "/export/root/templates";
static char	stringhold[MAXPATHLEN];

/* Local Globals */

#define	CLIENT_TO_BE_UPGRADED	0x0001

int		g_is_swm = 0;
char		*g_swmscriptpath;
struct client	*g_client_list;

/* Public Function Prototypes */
int	swi_load_clients(void);
int	swi_load_zones(void);
void	swi_update_action(Module *);
int	swi_upg_select_locale(Module *, char *);
int	swi_upg_deselect_locale(Module *, char *);
void	set_disklessclient_mode(void);
void	unset_disklessclient_mode(void);

/* Library function protypes */
int	is_server(void);
void	mark_preserved(Module *);
void	mark_removed(Module *);
Module *get_localmedia(void);
boolean_t	is_nonglobal_zone(Module *);
int 	is_KBI_service(Product *);

/* Library Function Prototypes */
int	update_module_actions(Module *, Module *, Action, Environ_Action);
char	*split_name(char **);
void	unreq_nonroot(Module *);
Modinfo *find_new_package(Product *, char *, char *, Arch_match_type *);
int	debug_bkpt(void);
Arch_match_type 		compatible_arch(char *, char *);

/* Local Function Prototypes */

static struct client	*find_clients(void);
static int		process_package(Module *, Modinfo *, Action,
    Environ_Action);
static void 		mark_cluster_tree(Module *, Module *);
static int		mark_action(Node *, caddr_t);
static int		mark_module_tree(Module *, Module *, Action,
    Environ_Action);
static void		mark_cluster_selected(char *);
static char		*genspooldir(Modinfo *);
static int 		set_patch_action(Node *, caddr_t);
static void		_set_patch_action(Modinfo *mi);
static int 		set_dflt_action(Node *, caddr_t);
static void 		_set_dflt_action(Modinfo *, Module *);
static void 		process_cluster(Module *);
static void 		mark_required_metacluster(Module *);
static void 		set_inst_dir(Module *, Modinfo *, Modinfo *);
static int 		cluster_match(char *, Module *);
static void 		spool_selected_arches(char *);
static int 		is_arch_selected(char *);
static int 		is_arch_supported(char *);
static int 		unreq(Node *, caddr_t);
static void 		reset_action(Module *);
static void 		reset_cluster_action(Module *);
static int		reset_instdir(Node *, caddr_t);
static int 		_reset_cluster_action(Node *, caddr_t);
static void 		reprocess_package(Module *, Modinfo *);
static void		reprocess_module_tree(Module *, Module *);
static int 		set_alt_clsstat(int selected, Module *);
static void		update_patch_status(Product *);
static void		diff_rev(Modinfo *, Modinfo *);
static void		set_instances_action(Modinfo *mi, Action data);
static void		resolve_references(Module *);


void		 unreq_nonroot(Module *mod);
int		 check_if_diskless(void);

#define	REQUIRED_METACLUSTER "SUNWCreq"

static Product		*g_newproduct = NULL;
static Module		*g_newproductmod = NULL;

static ActionCodeMode	action_mode = PRESERVE_IDENTICAL_PACKAGES;

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * is_server()
 * Parameters:
 *	none
 * Return:
 *	0	-
 *	1	-
 * Status:
 *	public
 */
int
is_server(void)
{
	Module *mod;

	for (mod = get_media_head(); mod != NULL; mod = mod->next)
		if (mod->info.media->med_type == INSTALLED_SVC &&
			!(mod->info.media->med_flags & SVC_TO_BE_REMOVED))  {
			return (1);
		}
	return (0);
}

/*
 * is_KBI_service()
 *
 * Parameters:
 *	prod - 	a pointer to the product module containing service in
 *		question.
 * Return:
 *	1 - if the product is a post KBI product
 *	0 - if the procudt is a pre KBI product.
 * Status:
 *	semi-private
 */
int
is_KBI_service(Product *prod)
{
	/*
	 * This is a quick and dirty way of determining a post-KBI
	 * service. If the version of the OS is 2.5 or greater then it
	 * is a post-KBI service.
	 * THIS WILL HAVE TO CHANGE IN THE FUTURE IF A BETTER WAY IS
	 * FOUND.
	 */

	char	version_string[50];

	if (prod->p_name == NULL || prod->p_version == NULL)
		return (0);

	(void) snprintf(version_string, sizeof (version_string), "%s_%s",
	    prod->p_name, prod->p_version);

	if (prod_vcmp(version_string, "Solaris_2.5") >= 0)
		return (1);	/* A version, 2.5 or higher */
	else
		return (0);	/* Less than 2.5 */
}

/*
 * update_module_actions()
 * Parameters:
 *	media_mod	-
 *	prodmod		-
 *	action		-
 *	env_action	-
 * Return:
 *	none
 * Status:
 *	public
 */
int
update_module_actions(Module * media_mod, Module * prodmod, Action action,
    Environ_Action env_action)
{
	Module	*mod, *mod2;
	Modinfo *mi;
	int	retval;

	if (media_mod == NULL || media_mod->sub == NULL)
		return (ERR_INVALID);
	g_newproductmod = prodmod;
	g_newproduct = prodmod->info.prod;
	reset_action(media_mod);
	reset_cluster_action(media_mod);

	walklist(g_newproductmod->info.prod->p_packages, reset_instdir,
	    (caddr_t)0);

	mark_required_metacluster(prodmod);

	/* process the installed metacluster */
	for (mod = media_mod->sub->sub; mod != NULL; mod = mod->next)
		if (mod->type == METACLUSTER) {
			mark_cluster_tree(media_mod, mod);
			retval = mark_module_tree(media_mod, mod, action,
			    env_action);
			if (retval != SUCCESS)
				return (retval);
			break;
		}

	/*
	 * Now process the other packages, looking for packages
	 * that are installed but that are not in the installed
	 * metacluster.
	 */

	for (mod = media_mod->sub->sub; mod != NULL; mod = mod->next) {
		if (mod->type == METACLUSTER)
			continue;
		if (mod->type == CLUSTER)
			mark_cluster_tree(media_mod, mod);
		retval = mark_module_tree(media_mod, mod, action, env_action);
		if (retval != SUCCESS)
			return (retval);
	}

	/*
	 * Set up the actions for the currently installed localization
	 * packages and the new versions.
	 */
	for (mod = media_mod->sub->info.prod->p_locale; mod != NULL;
	    mod = mod->next) {
		for (mod2 = mod->sub; mod2 != NULL; mod2 = mod2->next) {
			mi = mod2->info.mod;
			if (mi->m_shared != NULLPKG) {
				retval = process_package(media_mod, mi,
					action, env_action);
				if (retval != SUCCESS)
					return (retval);
			}
			while ((mi = next_inst(mi)) != NULL)
				if (mi->m_shared != NULLPKG) {
					retval = process_package(media_mod, mi,
					    action, env_action);
					if (retval != SUCCESS)
						return (retval);
				}
		}
	}

	/*
	 * now set up the action and basedir fields for all
	 * remaining packages in the media tree
	 */
	walklist(prodmod->info.prod->p_packages, set_dflt_action,
	    (caddr_t)media_mod);

	/* set selected geos */
	mod = media_mod->sub->info.prod->p_geo;
	if (mod) {
		while (mod != NULL) {
			if (mod->info.geo->g_selected)
				select_geo(prodmod, mod->info.geo->g_geo);
			mod = mod->next;
		}
	}

	/* set selected locales */
	mod = media_mod->sub->info.prod->p_locale;
	if (mod) {
		while (mod != NULL) {
			if (mod->info.locale->l_selected)
				select_locale(prodmod,
					mod->info.locale->l_locale, FALSE);
			mod = mod->next;
		}
	}

	/* clean up the cluster actions */
	for (mod = media_mod->sub->sub; mod != NULL; mod = mod->next)
		set_cluster_status(mod);

	/* mark any new l10n packages */
	sync_l10n(prodmod);

	/* set the action codes for all patch packages */
	walklist(media_mod->sub->info.prod->p_packages, set_patch_action,
	    (caddr_t)0);

	/* update the status of the patches */
	update_patch_status(media_mod->sub->info.prod);

	return (SUCCESS);
}

/*
 * split_name()
 * Parameters:
 *	cpp	-
 * Return:
 * Status:
 *	public
 */
char *
split_name(char ** cpp)
{
	char *wstart, *wend;
	int n;

	if (*cpp != NULL && **cpp != NULL) {
		wstart = *cpp;
		if (isspace(*wstart)) {
			/* Odd - we started in whitespace.  Move out of it */
			while (isspace(*wstart)) {
				wstart++;
			}
		}
		wend = wstart;

		/* Find the end of the current word */
		while (*wend && !isspace(*wend)) {
			wend++;
		}

		if (wend == wstart) {
			/* There's no word */
			*cpp = wend;
			return (NULL);
		}

		if (*wend) {
			/* Copying from the middle */
			n = (ptrdiff_t)wend - (ptrdiff_t)wstart;
			(void) strncpy(stringhold, wstart, n);
			stringhold[n] = '\0';
		} else {
			/* Copying from the end */
			(void) strcpy(stringhold, wstart);
		}

		/*
		 * Set the pointer for the next read to the start of the
		 * next word (if any)
		 */
		while (isspace(*wend)) {
			wend++;
		}

		*cpp = wend;

		return (stringhold);
	} else {
		return (NULL);
	}
}

/*
 * mark_preserved()
 *	Takes a module pointer to a media struct
 * Parameters:
 *	mod	-
 * Return:
 *	none
 * Status:
 *	public
 */
void
mark_preserved(Module * mod)
{
	Module	*prodmod;

	prodmod = mod->sub;
	while (prodmod) {
		walklist(prodmod->info.prod->p_packages, mark_action,
		    (caddr_t)TO_BE_PRESERVED);
		prodmod = prodmod->next;
	}
}

/*
 * mark_removed()
 * 	Takes a module pointer to a media struct
 * Parameters:
 *	mod	-
 * Return:
 *	none
 * Status:
 *	public
 */
void
mark_removed(Module *mod)
{
	Module	*prodmod;

	prodmod = mod->sub;
	while (prodmod) {
		walklist(prodmod->info.prod->p_packages, mark_action,
		    (caddr_t)TO_BE_REMOVED);
		prodmod = prodmod->next;
	}
}

/*
 * load_clients()
 * Parameters:
 *	none
 * Return:
 * Status:
 *	public
 */
int
swi_load_clients(void)
{
	struct client		*clientptr;

	if (is_server()) {
		g_client_list = find_clients();
		for (clientptr = g_client_list; clientptr != NULL;
			clientptr = clientptr->next_client) {
			load_installed(clientptr->client_root, FALSE);
		}
	}
	return (0);
}

/*
 * load_zones()
 *	Iterate through all upgradeable zones and load their installed
 *	software data into internal structures.
 *
 * Parameters:
 *	none
 * Return:
 *	SUCCESS		- All upgradeable zones have their installed
 *			software data loaded.
 *	FAILURE		- Failed to load installed software data
 *			for an upgradeable zone.
 * Status:
 *	public
 */
int
swi_load_zones(void)
{
	zoneList_t		zlst;
	int			k;
	char			*zonePath;
	char			*zoneName;
	char			zone_root[MAXPATHLEN];
	Module			*zone_mod, *m;
	Product			*zone_prod;

	int			child_pid;
	int			child_status;
	pid_t			retval;
	zoneid_t		zoneid;

	int			tmpl_fd;
	boolean_t		iserr = B_FALSE;
	FILE			*zfd;
	int			zpipe[2] = {0, 0};
	int			ret_code = SUCCESS;

	if (!z_zones_are_implemented())
		return (SUCCESS);

	zlst = z_get_nonglobal_zone_list();
	if (zlst == (zoneList_t)NULL) {
		return (SUCCESS);
	}

	/* Set up contract template for child */
	tmpl_fd = open64(CTFS_ROOT "/process/template", O_RDWR);
	if (tmpl_fd == -1) {
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Could not set up contract template for child"));
		return (FAILURE);
	}

	/*
	 * Child process doesn't do anything with the contract.
	 * Deliver no events, don't inherit, and allow it to
	 * be orphaned.
	 */
	if (ct_tmpl_set_critical(tmpl_fd, 0) != 0) {
		iserr = B_TRUE;
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Could not write critical event set term"));
	}
	if (ct_tmpl_set_informative(tmpl_fd, 0) != 0) {
		iserr = B_TRUE;
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Could not write informative event set term"));
	}
	if (ct_pr_tmpl_set_fatal(tmpl_fd, CT_PR_EV_HWERR) != 0) {
		iserr = B_TRUE;
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Could not write fatal event set term"));
	}
	if (ct_pr_tmpl_set_param(tmpl_fd, CT_PR_PGRPONLY | CT_PR_REGENT) != 0) {
		iserr = B_TRUE;
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Could not write parameter set term"));
	}
	if (ct_tmpl_activate(tmpl_fd) != 0) {
		iserr = B_TRUE;
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Could not activate contract template"));
	}
	if (iserr) {
		(void) close(tmpl_fd);
		return (FAILURE);
	}

	/* Open files needed by zones */
	if (!open_zone_fd()) {
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Could not open special files to process zones"));
		return (FAILURE);
	}

	for (k = 0; (zoneName = z_zlist_get_zonename(zlst, k)) != (char *)NULL;
	    k++) {

		/* If zone state not installed, skip it */
		if ((z_zlist_get_current_state(zlst, k)) <
		    ZONE_STATE_INSTALLED) {
			write_message(LOGSCR, STATMSG, LEVEL0,
			    dgettext("SUNW_INSTALL_LIBSVC",
			    "Skipping load of uninstalled "
			    "non-global zone environment: %s"),
			    zoneName);
			continue;
		}

		zonePath = z_zlist_get_zonepath(zlst, k);
		(void) strlcpy(zone_root, z_make_zone_root(zonePath),
		    MAXPATHLEN);

		/*
		 * Open a pipe so that the child process can send its
		 * output back to us.
		 */
		if (pipe(zpipe) != 0) {
			write_message(LOGSCR, ERRMSG, LEVEL0,
			    dgettext("SUNW_INSTALL_SWLIB",
			    "Could not create pipe to process zone: %s"),
			    zoneName);
			ret_code = FAILURE;
			goto done;
		}

		/*
		 * fork off a child to load installed data
		 * for a non-global zone.
		 */
		if ((child_pid = fork()) == -1) {
			(void) ct_tmpl_clear(tmpl_fd);
			write_message(LOGSCR, ERRMSG, LEVEL0,
			    dgettext("SUNW_INSTALL_SWLIB",
			    "Could not fork to process zone: %s"), zoneName);
			ret_code = FAILURE;
			goto done;
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
			setbuf(zfd, NULL);

			/*
			 * In case any of stdin, stdout or stderr
			 * are streams, anchor them to prevent
			 * malicious I_POPs.
			 */
			(void) ioctl(STDIN_FILENO, I_ANCHOR);
			(void) ioctl(STDOUT_FILENO, I_ANCHOR);
			(void) ioctl(STDERR_FILENO, I_ANCHOR);

			if (zone_enter(zoneid) == -1) {
				(void) ct_tmpl_clear(tmpl_fd);

				write_message(LOGSCR, ERRMSG, LEVEL0,
				    dgettext("SUNW_INSTALL_SWLIB",
				    "Failed to zone_enter zone: %s"), zoneName);
				_exit(1);
			}

			/* We're running in the non-global zone */

			/*
			 * Create a new Media module based on the zone's
			 * root and set its zonename.
			 */
			zone_mod = add_media(zone_root);
			zone_mod->info.media->med_zonename =
				    xstrdup(zoneName);

			/* Load the zone's installed data */
			zone_mod = load_installed_zone(zone_root);
			if (zone_mod) {
				zone_prod = zone_mod->sub->info.prod;
				zone_prod->p_zonename =
				    xstrdup(zoneName);

				/* Send the data back to the global zone */
				if (write_module_to_pipe(zfd, zone_mod,
				    B_TRUE) != 0) {
					write_message(LOGSCR, ERRMSG, LEVEL0,
					    dgettext("SUNW_INSTALL_SWLIB",
					    "Failure writing nonglobal zone "
					    "module: %s"), zoneName);
					(void) fclose(zfd);
					_exit(1);
				}
				(void) fclose(zfd);
				_exit(0);
			} else {
				write_message(LOGSCR, ERRMSG, LEVEL0,
				    dgettext("SUNW_INSTALL_SWLIB",
				    "Failure loading nonglobal zone "
				    "environment: %s"), zoneName);
				(void) fclose(zfd);
				_exit(1);
			}
		}
		/* parent process */

		/* Close write side of pipe, and turn read side into stream. */
		(void) close(zpipe[1]);
		zfd = fdopen(zpipe[0], "r");
		setbuf(zfd, NULL);

		/*  process output generated from child process */
		zone_mod = read_module_from_pipe(zfd);
		(void) fclose(zfd);

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
			    "Failure loading nonglobal zone environment: %s"),
			    zoneName);
			ret_code = FAILURE;
			goto done;
		}

		if (!zone_mod) {
			write_message(LOGSCR, ERRMSG, LEVEL0,
			    dgettext("SUNW_INSTALL_SWLIB",
			    "Failure reading non-global zone module: %s"),
			    zoneName);
			ret_code = FAILURE;
			goto done;
		}

		/* resolve pointer references */
		resolve_references(zone_mod->sub);

		/* Set the zone's inheritedDirs */
		zone_prod = zone_mod->sub->info.prod;
		zone_prod->p_inheritedDirs =
		    z_zlist_get_inherited_pkg_dirs(zlst, k);

		/* Now add this zone's media module to the media list */
		for (m = get_media_head(); m->next != NULL; m = m->next)
			;
		m->next = zone_mod;
		zone_mod->prev = m;
		zone_mod->head = get_media_head();
		zone_mod->next = (Module *)NULL;
		zone_mod->parent = (Module *)NULL;
	}

	/* Close files needed by zones */
done:	close_zone_fd();

	return (ret_code);
}

/*
 * update_action()
 * The user has toggled a module in the main screen (which is the
 * system's own environment).  Now, make every other environment
 * agree with the user's choice.  Note: this is complex, because
 * some of the environments may already be in the same state as
 * the main environment.  Those environments must be left
 * untouched.  The logic must also take into account partial
 * clusters.  Partial clusters can have a partial status of either
 * SELECTED (there is at least one non-required package selected)
 * or UNSELECTED (all component packages are either REQUIRED or
 * UNSELECTED).  All partial clusters must have their status
 * changed to be consistent with the main cluster, which may
 * itself be PARTIALLY_SELECTED.  Here's the logic for clusters (it's obvious
 * for packages) :
 *
 *		    Module Status of Cluster in Alternate Environment
 *
 *		   SELECTED	UNSELECTED	PARTIALLY_SELECTED
 * Mod Status
 * of cluster in ---------------------------------------------------
 * main env.	 |	      |		    | toggle module;
 *		 |	      |		    | if (still PARTIALLY_SELECTED)
 *   SELECTED	 | no action  |	toggle	    |    toggle module again
 *		 |--------------------------------------------------
 *		 |	      |		    | if (partial_status ==
 *   UNSELECTED  | toggle     |	no action   |    SELECTED) toggle
 *		 |--------------------------------------------------
 *		 |	      |		    | if (partial_status ==
 *   PARTIAL	 | toggle     |	no action   |    SELECTED) toggle
 *		 |--------------------------------------------------
 *
 * Note that an incoming cluster status of PARTIALLY_SELECTED is equivalent to
 * to UNSELECTED.  This is because the result of toggling a cluster
 * is never PARTIALLY_SELECTED with a partial_status of SELECTED.
 * Parameters:
 *	toggled_mod	-
 * Return:
 *	none
 * Status:
 *	public
 */
void
swi_update_action(Module * toggled_mod)
{
	Module	*mod;
	Node	*node;
	Module	*mediamod;
	char	id[MAXPKGNAME_LENGTH];
	int	selected, change_made;

	mediamod = get_localmedia();

	/* load the view for the global root */
	load_view(g_newproductmod, mediamod);

	reprocess_module_tree(mediamod, mediamod->sub);
	mark_arch(g_newproductmod);
	sync_l10n(g_newproductmod);
	/* set the action codes for all patch packages */
	walklist(mediamod->sub->info.prod->p_packages, set_patch_action,
	    (caddr_t)0);
	update_patch_status(mediamod->sub->info.prod);

	mod = toggled_mod;
	(void) strcpy(id, mod->info.mod->m_pkgid);
	selected = mod->info.mod->m_status;

	if (selected == REQUIRED)
		return;

	/* find the same module in every view and update it also */

	mediamod = get_media_head();
	while (mediamod != NULL) {
		change_made = 0;
		if ((mediamod->info.media->med_type == INSTALLED_SVC ||
		    mediamod->info.media->med_type == INSTALLED) &&
		    mediamod != get_localmedia() &&
		    has_view(g_newproductmod, mediamod) == SUCCESS) {
			(void) load_view(g_newproductmod, mediamod);
			if (mod->type == CLUSTER) {
				node = findnode(g_newproduct->p_clusters, id);
				if (node == NULL)
					continue;
				change_made = set_alt_clsstat(selected,
					(Module *)(node->data));
			} else if (mod->type == PACKAGE) {
				node = findnode(g_newproduct->p_packages, id);
				if (node == NULL)
					continue;
				if (((Modinfo *)(node->data))->m_status !=
					selected) {
					((Modinfo *)(node->data))->m_status =
						selected;
					change_made = 1;
				}
			}
			if (change_made) {
				reprocess_module_tree(mediamod, mediamod->sub);
				/* if a client */
				if (mediamod->info.media->med_type ==
				    INSTALLED &&
				    mediamod->info.media->med_zonename ==
				    NULL) {
					unreq_nonroot(g_newproductmod);
					set_primary_arch(g_newproductmod);
				} else {
					mark_arch(g_newproductmod);
				}
				sync_l10n(g_newproductmod);
				/*
				 *  set the action codes for all patch packages
				 */
				walklist(mediamod->sub->info.prod->p_packages,
				    set_patch_action, (caddr_t)0);
				update_patch_status(mediamod->sub->info.prod);
			}
		}
		mediamod = mediamod->next;
	}
	(void) load_view(g_newproductmod, get_localmedia());
}

/*
 * upg_select_locale()
 * Parameters:
 *	prodmod	-
 *	locale	-
 * Return:
 *	ERR_INVALIDTYPE	- 'prodmod' is neither a PRODUCT or NULLPRODUCT
 *	ERR_BADLOCALE	- 'locale' is not part of the locale chain for 'prodmod'
 *	SUCCESS		- locale structure of type 'locale' set successfully
 * Status:
 *	public
 */
int
swi_upg_select_locale(Module *prodmod, char *locale)
{
	Module *mediamod;
	int ret, final_ret;

	final_ret = SUCCESS;

	mediamod = get_media_head();
	while (mediamod != NULL) {
		if ((mediamod->info.media->med_type == INSTALLED_SVC ||
		    mediamod->info.media->med_type == INSTALLED) &&
		    has_view(prodmod, mediamod) == SUCCESS) {
			(void) load_view(prodmod, mediamod);
			ret = select_locale(prodmod, locale, TRUE);

			if (ret != SUCCESS)
				final_ret = ret;
		}
		mediamod = mediamod->next;
	}
	(void) load_view(prodmod, get_localmedia());

	return (final_ret);
}

/*
 * upg_deselect_locale()
 * Parameters:
 *	prodmod	-
 *	locale	-
 * Return:
 *	none
 * Status:
 *	public
 */
int
swi_upg_deselect_locale(Module *prodmod, char *locale)
{
	Module *mediamod, *m;
	int	locale_loaded;

	mediamod = get_media_head();
	while (mediamod != NULL) {
		if ((mediamod->info.media->med_type == INSTALLED_SVC ||
		    mediamod->info.media->med_type == INSTALLED) &&
		    mediamod->sub != NULL &&
		    has_view(prodmod, mediamod) == SUCCESS) {
			(void) load_view(prodmod, mediamod);
			locale_loaded = FALSE;
			for (m = mediamod->sub->info.prod->p_locale;
				m != NULL; m = m->next) {
				if (streq(locale, m->info.locale->l_locale) &&
					m->info.locale->l_selected)
					locale_loaded = TRUE;
			}
			if (locale_loaded == FALSE) {
				deselect_locale(prodmod, locale);
			}
		}
		mediamod = mediamod->next;
	}
	(void) load_view(prodmod, get_localmedia());

	return (SUCCESS);
}

/*
 * set_disklessclient_mode()
 *	Set the diskless client mode to skip the ZONE_SPOOLED check.
 * Parameters:
 *      none
 * Return:
 * Status:
 *      public
 */
void
set_disklessclient_mode(void) {
	diskless_install = 1;
}

/*
 * unset_disklessclient_mode()
 *	Unset the diskless client mode.
 * Parameters:
 *      none
 * Return:
 * Status:
 *      public
 */
void
unset_disklessclient_mode(void) {
	diskless_install = 0;
}

/*
 * upg_select_geo()
 *	Select the geographic region on the images being upgraded.  This routine
 *	also selects the geo's constituent locales.
 * Parameters:
 *	prodmod	- The module in which the geo is to be selected
 *	geo	- The region to be selected
 * Return:
 *	ERR_INVALIDTYPE	- 'prodmod' is neither a PRODUCT or a NULLPRODUCT
 *	ERR_BADLOCALE	- 'geo' is not part of the geographic region
 *				  chain for 'prodmod'
 *	SUCCESS		- geographic region successfully selected
 * Status:
 *	public
 */
int
swi_upg_select_geo(Module *prodmod, char *geo)
{
	Module *mediamod;
	int ret, final_ret;

	final_ret = SUCCESS;

	mediamod = get_media_head();
	while (mediamod != NULL) {
		if ((mediamod->info.media->med_type == INSTALLED_SVC ||
		    mediamod->info.media->med_type == INSTALLED) &&
		    has_view(prodmod, mediamod) == SUCCESS) {
			(void) load_view(prodmod, mediamod);
			ret = select_geo(prodmod, geo);

			if (ret != SUCCESS)
				final_ret = ret;
		}
		mediamod = mediamod->next;
	}
	(void) load_view(prodmod, get_localmedia());

	return (final_ret);
}

/*
 * upg_deselect_geo()
 *	Deselect the geographic region on the images being upgraded.  This
 *	routine also deselects the geo's constituent locales.
 * Parameters:
 *	prodmod	- The module in which the geo is to be deselected
 *	geo	- The region to be selected
 * Return:
 *	SUCCESS	- selection succeeded
 *	FAILURE	- selection failed
 * Status:
 *	public
 */
int
swi_upg_deselect_geo(Module *prodmod, char *geo)
{
	Module *mediamod, *m;
	int	geo_loaded;

	mediamod = get_media_head();
	while (mediamod != NULL) {
		if ((mediamod->info.media->med_type == INSTALLED_SVC ||
		    mediamod->info.media->med_type == INSTALLED) &&
		    mediamod->sub != NULL &&
		    has_view(prodmod, mediamod) == SUCCESS) {
			(void) load_view(prodmod, mediamod);
			geo_loaded = FALSE;
			for (m = mediamod->sub->info.prod->p_geo;
			    m != NULL; m = m->next) {
				if (streq(geo, m->info.geo->g_geo) &&
				    m->info.geo->g_selected) {
					geo_loaded = TRUE;
				}
			}
			if (geo_loaded == FALSE) {
				deselect_geo(prodmod, geo);
			}
		}
		mediamod = mediamod->next;
	}
	(void) load_view(prodmod, get_localmedia());

	return (SUCCESS);
}

/*
 * get_localmedia()
 * Parameters:
 *	none
 * Return:
 *
 * Status:
 *	public
 */
Module *
get_localmedia(void)
{
	Module *mod;

	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type == INSTALLED &&
		    strcmp(mod->info.media->med_dir, "/") == 0 &&
		    mod->info.media->med_zonename == NULL)
			return (mod);
	}
	return ((Module *)NULL);
}

/*
 * is_nonglobal_zone()
 *
 * Parameters:
 *     Media module
 * Return:
 *     B_TRUE	- if module represents a local zone media
 *     B_FALSE	- if not
 * Status:
 *     Public
 */
boolean_t
is_nonglobal_zone(Module *mod) {

	if (mod == NULL)
		return (B_FALSE);

	if (mod->type != MEDIA)
		return (B_FALSE);

	if (mod->info.media->med_zonename != NULL)
		return (B_TRUE);
	else
		return (B_FALSE);
}


/*
 * unreq_nonroot()
 * Parameters:
 *	mod	-
 * Return:
 *	none
 * Status:
 *	public
 */
void
unreq_nonroot(Module * mod)
{
	walklist(mod->info.prod->p_packages, unreq, (caddr_t)0);
	while (mod != NULL) {
		if (mod->type == METACLUSTER &&
		    strcmp(mod->info.mod->m_pkgid,
			REQUIRED_METACLUSTER) == 0) {
			set_cluster_status(mod);
			break;
		}
		mod = mod->next;
	}
}

/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * unreq()
 * Parameters:
 *	np	- node pointer
 *	data	- ignored
 * Return:
 * Status:
 *	private
 */
/*ARGSUSED1*/
static int
unreq(Node * np, caddr_t data)
{
	Modinfo	*mi;

	mi = (Modinfo *)(np->data);
	if (mi->m_shared != NULLPKG && mi->m_sunw_ptype != PTYPE_ROOT) {
		mi->m_status = UNSELECTED;
		mi->m_action = CANNOT_BE_ADDED_TO_ENV;
	}
	while ((mi = next_inst(mi)) != NULL) {
		if (mi->m_sunw_ptype != PTYPE_ROOT) {
			mi->m_status = UNSELECTED;
			mi->m_action = CANNOT_BE_ADDED_TO_ENV;
		}
	}
	return (0);
}

/*
 * set_dflt_action()
 * Parameters:
 *	np	-
 *	data	-
 * Return:
 * Status:
 *	private
 */
static int
set_dflt_action(Node * np, caddr_t data)
{
	Modinfo	*mi;
	Module *media_mod;

	mi = (Modinfo *)(np->data);
	/*LINTED [alignment ok]*/
	media_mod = (Module *)data;
	_set_dflt_action(mi, media_mod);
	while ((mi = next_inst(mi)) != NULL)
		_set_dflt_action(mi, media_mod);
	return (0);
}

/*
 * _set_dflt_action()
 * Parameters:
 *	mi	  -
 *	media_mod -
 * Return:
 *	none
 * Status:
 *	private
 */
static void
_set_dflt_action(Modinfo * mi, Module * media_mod)
{
	if (mi->m_shared != NULLPKG && mi->m_action == NO_ACTION_DEFINED) {
		if (mi->m_sunw_ptype == PTYPE_ROOT) {
			if (media_mod->info.media->med_type == INSTALLED)
				mi->m_action = TO_BE_PKGADDED;
			else
				mi->m_action = TO_BE_SPOOLED;
		} else {
			if (media_mod->info.media->med_type == INSTALLED)
				mi->m_action = TO_BE_PKGADDED;
			else { /* it's a service */
				/*
				 *  In 2.1, opt packages have a SUNW_PKGTYPE
				 *  of usr and a basedir of /opt.  In 2.2,
				 *  opt packages have a SUNW_PKGTYPE of
				 *  UNKNOWN.
				 */
				if (mi->m_sunw_ptype == PTYPE_UNKNOWN ||
				    (mi->m_sunw_ptype == PTYPE_USR &&
					streq(mi->m_basedir, "/opt")) ||
					streq(mi->m_arch, "all")) {
					mi->m_action =
						CANNOT_BE_ADDED_TO_ENV;
					return;
				}

				if (media_mod->info.media->med_flags &
					SPLIT_FROM_SERVER) {
					if (supports_arch(
						get_default_arch(), mi->m_arch))
						mi->m_action =
							ADDED_BY_SHARED_ENV;
					else
						mi->m_action = TO_BE_PKGADDED;
				} else
					mi->m_action = TO_BE_PKGADDED;
			}
		}
		if (mi->m_action == TO_BE_PKGADDED ||
			mi->m_action == TO_BE_SPOOLED)
			set_inst_dir(media_mod, mi, NULL);
	}
}

/*
 * mark_module_tree()
 * Parameters:
 *	media_mod	-
 *	mod		-
 *	action		-
 *	env_action
 * Return:
 *	none
 * Status:
 *	private
 */
static int
mark_module_tree(Module *media_mod, Module *mod, Action action,
    Environ_Action env_action)
{
	Modinfo *mi;
	Module	*child;
	int	retval;

	/*
	 * Do a depth-first search of the module tree, marking
	 * modules appropriately.
	 */
	mi = mod->info.mod;
	if (mod->type == PACKAGE) {
		/*
		 * When the service is of a different ISA than the server,
		 * and the package doesn't exist for the native ISA, the
		 * module at the head of the instance chain will be a
		 * spooled package, not a NULLPKG, so don't assume that
		 * when we're looking at a root package for a service, that
		 * the first instance is necessarily a NULLPKG.
		 */
		if ((!(media_mod->info.media->med_type == INSTALLED_SVC &&
		    (media_mod->info.media->med_flags & SPLIT_FROM_SERVER) &&
		    mi->m_sunw_ptype == PTYPE_ROOT)) ||
		    mi->m_shared != NULLPKG) {
			retval = process_package(media_mod, mi, action,
			    env_action);
			if (retval != SUCCESS)
				return (retval);
		}
	}
	for (mi = next_inst(mi); mi != NULL; mi = next_inst(mi)) {
		retval = process_package(media_mod, mi, action,
		    env_action);
		if (retval != SUCCESS)
			return (retval);
	}
	child = mod->sub;
	while (child) {
		retval = mark_module_tree(media_mod, child, action, env_action);
		if (retval != SUCCESS)
			return (retval);
		child = child->next;
	}
	return (SUCCESS);
}

/*
 * reprocess_module_tree()
 * Parameters:
 *	media_mod	-
 *	mod		-
 * Return:
 *
 * Status:
 *	private
 */
static void
reprocess_module_tree(Module * media_mod, Module * mod)
{
	Modinfo *mi;
	Node	*node;
	Module	*child, *lm;

	/*
	 * Do a depth-first search of the module tree, marking
	 * modules appropriately.
	 */
	if (mod->type == PACKAGE) {
		mi = mod->info.mod;
		if ((!(media_mod->info.media->med_type == INSTALLED_SVC &&
			mi->m_sunw_ptype == PTYPE_ROOT)) ||
			mi->m_shared != NULLPKG)
			reprocess_package(media_mod, mi);
		while ((node = mi->m_instances) != NULL) {
			mi = (Modinfo *)(node->data);
			reprocess_package(media_mod, mi);
		}
	} else if (mod->type == NULLPRODUCT) {
		/*
		 * If we're looking at the product, go hit all of the
		 * L10N packages.
		 */
		for (lm = mod->info.prod->p_locale; lm; lm = lm->next) {
			if (lm->sub) {
				for (child = lm->sub; child;
					child = child->next) {
					reprocess_module_tree(media_mod, child);
				}
			}
		}
	}

	child = mod->sub;
	while (child) {
		reprocess_module_tree(media_mod, child);
		child = child->next;
	}
}

/*
 * mark_cluster_tree()
 * Parameters:
 *	media_mod	-
 *	mod		-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
mark_cluster_tree(Module *media_mod, Module *mod)
{
	Module	*child;

	/*
	 * Do a depth-first search of the module tree, marking
	 * modules appropriately.
	 */
	if (mod->type == CLUSTER || mod->type == METACLUSTER)
		process_cluster(mod);
	child = mod->sub;
	while (child) {
		mark_cluster_tree(media_mod, child);
		child = child->next;
	}
}

/*
 * process_cluster()
 * Parameters:
 *	mod	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
process_cluster(Module * mod)
{
	Modinfo *mi;
	char	*cp, *p;

	mi = mod->info.mod;
	/*
	 * if action is not NO_ACTION_DEFINED, we've already
	 * looked at it.
	 *
	 * metaclusters are processed even if they are only
	 * partially selected.  Regular clusters are only
	 * processed if they are fully selected.
	 */

	if (mi->m_action != NO_ACTION_DEFINED ||
		(mod->type == CLUSTER && mi->m_status != SELECTED) ||
		mi->m_status == UNSELECTED)
		return;

	if (mi->m_pkg_hist != NULL) {
		cp = mi->m_pkg_hist->replaced_by;
		while ((p = split_name(&cp)) != NULL)
			mark_cluster_selected(p);
	}
	if (mi->m_pkg_hist == NULL || !mi->m_pkg_hist->to_be_removed)
		mark_cluster_selected(mi->m_pkgid);

	mi->m_action = TO_BE_REPLACED;
}

/*
 * get_sub_cluster()
 * Parameters:
 *      char *p -
 * Return:
 *      The meta cluster that is contained within the p meta cluster. WARNING
 *      this is a hack. In the software library there is no real hierarchical
 *      sense of metaclusters. We need this hack because x86 does not have
 *      an SUNWCxall meta cluster so mark_cluster_selected will never mark
 *      a cluster for it if we are doing a nonnative upgrade for x86 and the
 *      native machine has SUNWCxall installed. This hack solves that problem
 *      but please know that this is a hack.
 *
 *      rboykin
 *
 * Status:
 *      private
 */
static char *
get_sub_cluster(char *p)
{
	if (strcmp("SUNWCXall", p) == 0)
		return ("SUNWCall");
	else if (strcmp("SUNWCall", p) == 0)
		return ("SUNWCprog");
	else if (strcmp("SUNWCprog", p) == 0)
		return ("SUNWCuser");
	else if (strcmp("SUNWCuser", p) == 0)
		return ("SUNWCreq");
	else
		return (NULL);
}

/*
 * mark_cluster_selected()
 * Parameters:
 *	p	-
 * Return:
 *
 * Status:
 *	private
 */
static void
mark_cluster_selected(char *p)
{
	Node	*node;
	Module	*mod;

	node = findnode(g_newproduct->p_clusters, p);

	while (!node && p) {
		p = get_sub_cluster(p);

		if (p)
			node = findnode(g_newproduct->p_clusters, p);
		else
			node = NULL;
	}

	if (node) {
		mod = (Module *)(node->data);
		mark_module(mod, SELECTED);
	}
}

/*
 * find_new_package()
 * Parameters:
 *	prod	 -
 *	id	 -
 *	arch	 -
 *	archmatch -
 * Return:
 * Status:
 *	private
 */
Modinfo *
find_new_package(Product *prod, char *id, char *arch, Arch_match_type *match)
{
	Node	*node, *savenode;
	Modinfo *mi;

	*match = PKGID_NOT_PRESENT;
	node = findnode(prod->p_packages, id);
	savenode = node;
	if (node) {
		mi = (Modinfo *)(node->data);
		if (arch == NULL)
			return (mi);

		/*
		 *  ARCH_NOT_SUPPORTED means that the architecture isn't
		 *  supported at all by the installation media (example:
		 *  currently installed package has arch=sparc, but the
		 *  installation CD is for intel.  We don't want to
		 *  remove the sparc packages just because they don't
		 *  have replacements on the installation CD.)
		 *  NO_ARCH_MATCH means that the architecture is supported
		 *  on the installation CD, but that there is no replacement
		 *  package (a package with compatible architecture) for
		 *  this particular package.
		 */
		if (!is_arch_supported(arch)) {
			*match = ARCH_NOT_SUPPORTED;
			return (NULL);
		}
		*match = NO_ARCH_MATCH;
		if (mi->m_shared != NULLPKG) {
			*match = compatible_arch(arch, mi->m_arch);
			if (*match == ARCH_MATCH ||
			    *match == ARCH_LESS_SPECIFIC)
				return (mi);
		}
		while (*match == NO_ARCH_MATCH &&
		    (node = mi->m_instances) != NULL) {
			mi = (Modinfo *)(node->data);
			if (mi->m_shared != NULLPKG) {
				*match = compatible_arch(arch, mi->m_arch);
				if (*match == ARCH_MATCH ||
				    *match == ARCH_LESS_SPECIFIC)
					return (mi);
			}
		}
		if (*match == ARCH_MORE_SPECIFIC) {
			node = savenode;
			mi = (Modinfo *)(node->data);
			if (mi->m_shared != NULLPKG) {
				if (is_arch_selected(mi->m_arch))
					return (mi);
			}
			while ((node = mi->m_instances) != NULL) {
				mi = (Modinfo *)(node->data);
				if (mi->m_shared != NULLPKG)
					if (is_arch_selected(mi->m_arch))
						return (mi);
			}
		}
		return (NULL);
	}
	return (NULL);
}

/*
 * compatible_arch()
 * Parameters:
 *    char *oldarch
 *    char *newarch
 * Return:
 *    Arch_match_type
 *        ARCH_MATCH oldarch and newarch match exactly
 *        ARCH_MORE_SPECIFIC newarch is more specific than oldarch
 *        ARCH_LESS_SPECIFIC newarch is less specific than oldarch
 *        NO_ARCH_MATCH no match
 *
 * Status:
 *      Internal library function
 */
Arch_match_type
compatible_arch(char *oldarch, char *newarch)
{
	char *o_arch, *n_arch;
	char *o_endfield, *n_endfield;
	int o_len, n_len;

	o_arch = oldarch;
	n_arch = newarch;

	if (strcmp(o_arch, n_arch) == 0)
		return (ARCH_MATCH);
	if (strcmp(o_arch, "all") == 0)
		return (ARCH_MORE_SPECIFIC);
	if (strcmp(n_arch, "all") == 0)
		return (ARCH_LESS_SPECIFIC);
	while (*o_arch && *n_arch) {
		o_endfield = strchr(o_arch, '.');
		n_endfield = strchr(n_arch, '.');
		o_len = (o_endfield ?
				(ptrdiff_t)o_endfield - (ptrdiff_t)o_arch :
				strlen(o_arch));
		n_len = (n_endfield ?
				(ptrdiff_t)n_endfield - (ptrdiff_t)n_arch :
				strlen(n_arch));
		if (o_len != n_len)
			return (NO_ARCH_MATCH);
		if (strncmp(o_arch, n_arch, o_len) != 0)
			return (NO_ARCH_MATCH);
		if (o_endfield != NULL && n_endfield == NULL)
			return (ARCH_LESS_SPECIFIC);
		if (n_endfield != NULL && o_endfield == NULL)
			return (ARCH_MORE_SPECIFIC);
		if (n_endfield == NULL && o_endfield == NULL)
			return (ARCH_MATCH);
		o_arch += o_len+1;
		n_arch += o_len+1;
	}
	/*
	 *  If the architecture adheres to the standard, we should
	 *  never reach this point.
	 */
	if (*o_arch == '\0')
		(void) printf("Illegal architecture format: %s\n", oldarch);
	if (*n_arch == '\0')
		(void) printf("Illegal architecture format: %s\n", newarch);
	return (NO_ARCH_MATCH);
}

int
debug_bkpt(void)
{
	return (0);
}

/*
 * process_package()
 * Parameters:
 *	media_mod	-
 *	mi		-
 *	action		-
 *	env_action	-
 * Return:
 *	none
 * Status:
 *	private
 */
static int
process_package(Module *media_mod, Modinfo *mi, Action action,
    Environ_Action env_action)
{
	Modinfo  	*mnew, *imi;
	char		*cp, *p;
	Arch_match_type	archmatch;
	Product		*oldProd;
	Node		*node;

	if (mi->m_pkgid && streq(mi->m_pkgid, swdebug_pkg_name))
		(void) debug_bkpt();
	/*
	 * if action is not NO_ACTION_DEFINED, we've already
	 * looked at it.
	 */
	if (mi->m_action != NO_ACTION_DEFINED)
		return (SUCCESS);

	/*
	 *  If the package has a history entry with a REMOVE_FROM_CLUSTER
	 *  field, and the installed metacluster is one of the ones from
	 *  which this package is to be removed, mark it for removal.
	 */
	if (env_action == ENV_TO_BE_UPGRADED && mi->m_pkg_hist != NULL &&
		cluster_match(mi->m_pkg_hist->cluster_rm_list, media_mod)) {
		if (action == TO_BE_PRESERVED)
			mi->m_action = TO_BE_PRESERVED;
		else
			mi->m_action = TO_BE_REMOVED;
		mi->m_flags |= DO_PKGRM;
		mi->m_flags |= CONTENTS_GOING_AWAY;
		/*
		 * Also remove all of the instances of this packages. To do
		 * this we need to find the head of the instance chain, and
		 * mark all of the instances.
		 */
		if (media_mod->info.media->med_upg_from != (Module *)NULL)
			oldProd =
			media_mod->info.media->med_upg_from->sub->info.prod;
		else
			oldProd = media_mod->sub->info.prod;
		if ((node = findnode(oldProd->p_packages, mi->m_pkgid)) ==
		    NULL)
			return (FAILURE);

		set_instances_action((Modinfo *)node->data, TO_BE_REMOVED);

		return (SUCCESS);
	}

	/*
	 * This is some special case code for upgrading from a pre-KBI
	 * service to a post-KBI service. In this case the package type KVM
	 * is special. It is special because it special meaning in the pre-KBI
	 * world, but does not in post-KBI. So to solve some problems any
	 * package of type KVM will be explicitly marked as needing removal.
	 */
	/*
	 * NOTICE THIS CODE is TEMPORARY!!
	 * This code should be checking for upgrades between pre and post
	 * KBI systems. The check for old systems has been temporally
	 * removed due to problems with NULLPRODUCTs. This will be fixed in
	 * the future.
	 */
	if (env_action == ENV_TO_BE_UPGRADED &&
	    mi->m_sunw_ptype == PTYPE_KVM && is_KBI_service(g_newproduct)) {
		if (media_mod->info.media->med_upg_from != (Module *)NULL)
			oldProd =
			media_mod->info.media->med_upg_from->sub->info.prod;
		else
			oldProd = media_mod->sub->info.prod;
		/*
		 * Now make sure we are upgrading from a pre-KBI system
		 */
		if (! is_KBI_service(oldProd))
			for (imi = mi; imi != NULL; imi = next_inst(imi)) {
				imi->m_action = TO_BE_REMOVED;
				imi->m_flags |= DO_PKGRM;
			}
	}

	/*
	 *  Use the package history entry to map existing packages to
	 *  the packages that replace them.  Set the status and
	 *  actions for the replacement packages.  If the currently-
	 *  installed package will still be installed after the
	 *  the upgrade (that is, its "to_be_removed" value is
	 *  FALSE), its status won't be set in this block.  It will
	 *  be set in the next block.
	 */
	if (env_action == ENV_TO_BE_UPGRADED && mi->m_pkg_hist != NULL) {
		if (mi->m_pkg_hist->to_be_removed)
			if (action == TO_BE_PRESERVED)
				mi->m_action = TO_BE_PRESERVED;
			else
				mi->m_action = TO_BE_REMOVED;
		cp = mi->m_pkg_hist->replaced_by;
		while ((p = split_name(&cp)) != NULL) {
			mnew = find_new_package(g_newproduct, p, mi->m_arch,
			    &archmatch);
			if (mnew) {
				/*
				 *  If currently-installed pkg is a
				 *  NULLPKG, it was explicitly-removed
				 *  by the user.  Its replacement pkgs
				 *  should be UNSELECTED.
				 */
				if (mi->m_shared == NULLPKG) {
					if (mnew->m_status != REQUIRED)
						mnew->m_status = UNSELECTED;
					while ((mnew = next_inst(mnew)) != NULL)
						if (mnew->m_status != REQUIRED)
							mnew->m_status =
							    UNSELECTED;
				} else {
					if (mnew->m_status != REQUIRED)
						mnew->m_status = SELECTED;
					if (mi->m_shared == SPOOLED_NOTDUP)
						mnew->m_action = TO_BE_SPOOLED;
					else if (mi->m_shared == NOTDUPLICATE)
						mnew->m_action = TO_BE_PKGADDED;
					else /* it's a duplicate */
						mnew->m_action =
							ADDED_BY_SHARED_ENV;
					set_inst_dir(media_mod, mnew, NULL);
				}
			}
		}
	}
	if (env_action == ADD_SVC_TO_ENV || mi->m_pkg_hist == NULL ||
	    !mi->m_pkg_hist->to_be_removed) {
		mnew = find_new_package(g_newproduct, mi->m_pkgid,
		    mi->m_arch, &archmatch);
		if ((archmatch == PKGID_NOT_PRESENT ||
		    archmatch == ARCH_NOT_SUPPORTED) &&
		    mi->m_shared != NULLPKG) {
			mi->m_action = TO_BE_PRESERVED;
			if (archmatch == PKGID_NOT_PRESENT &&
			    mi->m_pkg_hist == NULL)
				mi->m_flags |= IS_UNBUNDLED_PKG;
			return (SUCCESS);
		}
		if (archmatch == NO_ARCH_MATCH && mi->m_shared != NULLPKG) {
			if (env_action == ADD_SVC_TO_ENV) {
				mi->m_action = TO_BE_PRESERVED;
				return (SUCCESS);
			}
			if (mi->m_shared == SPOOLED_NOTDUP) {
				mi->m_action = TO_BE_REMOVED;
				spool_selected_arches(mi->m_pkgid);
				return (SUCCESS);
			} else {
				mi->m_action = TO_BE_REMOVED;
				mi->m_flags |= DO_PKGRM;
				return (SUCCESS);
			}
		} else if (archmatch == ARCH_MORE_SPECIFIC &&
			    mi->m_shared != NULLPKG) {
			if (env_action == ADD_SVC_TO_ENV) {
				diff_rev(mi, mnew);
				return (ERR_DIFFREV);
			}
			if (mi->m_shared == SPOOLED_NOTDUP) {
				mi->m_action = TO_BE_REMOVED;
				spool_selected_arches(mi->m_pkgid);
				return (SUCCESS);
			}
			if (mnew == NULL) {
				mi->m_action = TO_BE_REMOVED;
				mi->m_flags |= DO_PKGRM;
				return (SUCCESS);
			}
		} else if (archmatch == ARCH_LESS_SPECIFIC &&
			    mi->m_shared != NULLPKG) {
			if (env_action == ADD_SVC_TO_ENV) {
				diff_rev(mi, mnew);
				return (ERR_DIFFREV);
			}
			if (mi->m_shared == SPOOLED_NOTDUP) {
				mi->m_action = TO_BE_REMOVED;
				spool_selected_arches(mi->m_pkgid);
				return (SUCCESS);
			}
		}
		if (mnew != NULL && mi->m_shared == NULLPKG) {
			if (mnew->m_status != REQUIRED)
				mnew->m_status = UNSELECTED;
			while ((mnew = next_inst(mnew)) != NULL)
				if (mnew->m_status != REQUIRED)
					mnew->m_status = UNSELECTED;
			return (SUCCESS);
		}
		if (mi->m_shared == SPOOLED_NOTDUP ||
			mi->m_shared == SPOOLED_DUP) {
			if (action == TO_BE_PRESERVED) {
				if (mnew != NULL) {
					if (mnew->m_status != REQUIRED)
						mnew->m_status = SELECTED;
					/*
					 * compare old vs. new VERSION
					 * numbers to see if we need
					 * to upgrade the package.
					 *
					 * If they are the same,
					 * and the package does not
					 * have a PKGRM=yes pkghistory
					 * entry, and the package's
					 * zone spool area has previously
					 * been populated, then we don't
					 * need to upgrade the package.
					 * If it is a diskless install
					 * skipping the ZONE_SPOOLED
					 * check since it is required
					 * only in upgrade.
					 * If we are processing a local zone,
					 * skip the ZONE_SPOOLED check as
					 * well since a local zone does not
					 * need the spool area populated.
					 */
					if (pkg_fullver_cmp(mnew, mi) ==
					    V_EQUAL_TO && action_mode ==
					    PRESERVE_IDENTICAL_PACKAGES &&
					    !(mi->m_pkg_hist &&
						mi->m_pkg_hist->needs_pkgrm) &&
					    (check_if_diskless() ||
					    is_nonglobal_zone(media_mod) ||
					    (mi->m_flags & ZONE_SPOOLED))) {
						mi->m_action = TO_BE_PRESERVED;
						mnew->m_action =
							EXISTING_NO_ACTION;
						if (mi->m_instdir)
							mnew->m_instdir =
								xstrdup(
								mi->m_instdir);
						else
							mnew->m_instdir =
								NULL;
					} else {
#ifndef IGNORE_DIFF_REV
						if (env_action ==
						    ADD_SVC_TO_ENV) {
							diff_rev(mi, mnew);
							return (ERR_DIFFREV);
						}
#else
						if (env_action ==
						    ADD_SVC_TO_ENV) {
							mi->m_action =
							    TO_BE_PRESERVED;
							mnew->m_action =
							    EXISTING_NO_ACTION;
							if (mi->m_instdir)
								mnew->m_instdir=
								xstrdup(
								mi->m_instdir);
							else
								mnew->m_instdir=
								NULL;
						}
#endif
						mi->m_action = TO_BE_REMOVED;
						mnew->m_action = TO_BE_SPOOLED;
					}
				} else
					mi->m_action = TO_BE_PRESERVED;
			} else {
				mi->m_action = TO_BE_REMOVED;
				if (mnew != NULL) {
					if (mnew->m_status != REQUIRED)
						mnew->m_status = SELECTED;
					mnew->m_action = TO_BE_SPOOLED;
				}
			}
		} else {
			if (mnew == NULL)
				mi->m_action = TO_BE_PRESERVED;
			/*
			 * compare old vs. new VERSION numbers to see
			 * if we need to upgrade the package.
			 *
			 * If they are the same, and the package does
			 * not have a PKGRM=yes pkghistory entry, and
			 * the package's zone spool area has
			 * previously been populated, then we don't
			 * need to upgrade the package.
			 * If it is a diskless install skipping the
			 * ZONE_SPOOLED check since it is
			 * required only in upgrade.
			 * If we are processing a local zone, skip
			 * the ZONE_SPOOLED check as well since a local
			 * zone does not need the spool area populated.
			 */
			else if (pkg_fullver_cmp(mnew, mi) == V_EQUAL_TO &&
			    action_mode == PRESERVE_IDENTICAL_PACKAGES &&
			    !(mi->m_pkg_hist &&
				mi->m_pkg_hist->needs_pkgrm) &&
			    (check_if_diskless() ||
			    is_nonglobal_zone(media_mod) ||
			    (mi->m_flags & ZONE_SPOOLED))) {
				mi->m_action = TO_BE_PRESERVED;
				if (mnew->m_status != REQUIRED)
					mnew->m_status = SELECTED;
				mnew->m_action = EXISTING_NO_ACTION;
				if (mi->m_instdir)
					mnew->m_instdir =
						xstrdup(mi->m_instdir);
				else
					mnew->m_instdir = NULL;
			} else {
#ifndef IGNORE_DIFF_REV
				if (env_action == ADD_SVC_TO_ENV) {
					diff_rev(mi, mnew);
					return (ERR_DIFFREV);
				}
#else
				if (env_action == ADD_SVC_TO_ENV) {
					mi->m_action = TO_BE_PRESERVED;
					if (mnew->m_status != REQUIRED)
						mnew->m_status = SELECTED;
					mnew->m_action = EXISTING_NO_ACTION;
					if (mi->m_instdir)
						mnew->m_instdir =
							xstrdup(mi->m_instdir);
					else
						mnew->m_instdir = NULL;
				}
#endif
				mi->m_action = action;
				if (mnew->m_status != REQUIRED)
					mnew->m_status = SELECTED;
				if (mi->m_shared == NOTDUPLICATE) {
					mnew->m_action = TO_BE_PKGADDED;
					if (!(mi->m_pkg_hist &&
					    mi->m_pkg_hist->needs_pkgrm))
						mnew->m_flags |=
						    INSTANCE_ALREADY_PRESENT;
					/*
					 * Also we need to remove all of
					 * the duplicate instances of this
					 * package before actually adding
					 * the new package.
					 */
					set_instances_action(mi,
					    TO_BE_REMOVED);
				} else { /* it's a duplicate */
				/*
				 * hack here:  if a package changes from
				 * being a "usr" package to a "root" package,
				 * it will appear as a duplicate in the
				 * service's media structure, but needs to
				 * be spooled in the new media structure.
				 * This check will fail if we tried to
				 * upgrade a non-native service (that is,
				 * non-shared), but since we don't do that,
				 * this check is adequate to fix the bug.
				 */
					if (mnew->m_sunw_ptype == PTYPE_ROOT)
						mnew->m_action = TO_BE_SPOOLED;
					else
						mnew->m_action =
						    ADDED_BY_SHARED_ENV;
				}
			}
		}
		if (mnew != NULL)
			set_inst_dir(media_mod, mnew, mi);
	}
	return (SUCCESS);
}

/*
 * reprocess_package()
 * Parameters:
 *	mi
 * Return:
 *	none
 * Status:
 *	private
 */
static void
reprocess_package(Module *media_mod, Modinfo *mi)
{
	Modinfo	*mnew;
	Arch_match_type	archmatch;
	int	cmpRet;

	if (mi->m_pkgid && streq(mi->m_pkgid, swdebug_pkg_name))
		(void) debug_bkpt();
	/*
	 * We only care about modules of type NOTDUPLICATE.  Spooled
	 * packages are always marked for removal.  Duplicate packages
	 * are not interesting because there is never an action
	 * associated with them.  We also don't care about packages
	 * with a to_be_removed flag set.  Since they are always
	 * removed, their status never changes.
	 */
	if (mi->m_shared != NOTDUPLICATE ||
	    (mi->m_pkg_hist && mi->m_pkg_hist->to_be_removed))
		return;

	/*
	 * See if package has a corresponding package in the
	 * new media structure.  If not, just return because
	 * there isn't any reason to reprocess it.
	 */
	mnew = find_new_package(g_newproduct, mi->m_pkgid, mi->m_arch,
			    &archmatch);

	if (mnew == NULL || mnew->m_shared == NULLPKG)
		return;

	if (mnew->m_status == UNSELECTED) {
		mi->m_action = TO_BE_REMOVED;
		mi->m_flags |= DO_PKGRM;
		mi->m_flags |= CONTENTS_GOING_AWAY;
		return;
	} else {
		/*
		 * compare old vs. new VERSION numbers to see if we
		 * need to upgrade the package.
		 *
		 * If they are the same, and the package does not have
		 * a PKGRM=yes pkghistory entry, and the package's
		 * zone spool area has previously been populated, then
		 * we don't need to upgrade the package.
		 */
		cmpRet = pkg_fullver_cmp(mnew, mi);
		if (cmpRet == V_EQUAL_TO &&
		    action_mode == PRESERVE_IDENTICAL_PACKAGES &&
		    !(mi->m_pkg_hist && mi->m_pkg_hist->needs_pkgrm) &&
		    ((mi->m_flags & ZONE_SPOOLED) ||
		    is_nonglobal_zone(media_mod))) {
			mi->m_action = TO_BE_PRESERVED;
			mnew->m_action = EXISTING_NO_ACTION;
		} else if (cmpRet == V_EQUAL_TO &&
			action_mode == REPLACE_IDENTICAL_PACKAGES) {
			mi->m_action = TO_BE_REPLACED;
			mnew->m_action = TO_BE_PKGADDED;
		} else {
			mi->m_action = TO_BE_REPLACED;
			if (!(mi->m_pkg_hist && mi->m_pkg_hist->needs_pkgrm))
				mnew->m_flags |= INSTANCE_ALREADY_PRESENT;
		}
		mi->m_flags &= ~DO_PKGRM;
		mi->m_flags &= ~CONTENTS_GOING_AWAY;
	}
}

/*
 * reset_action()
 *	Takes a module pointer to a media struct
 * Parameters:
 *	mod	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
reset_action(Module *mod)
{
	Module	*prodmod;

	prodmod = mod->sub;
	while (prodmod &&
	    (prodmod->type == PRODUCT || prodmod->type == NULLPRODUCT)) {
		walklist(prodmod->info.prod->p_packages, mark_action,
		    (caddr_t)NO_ACTION_DEFINED);
		prodmod = prodmod->next;
	}
}

/*
 * reset_cluster_action()
 *	Takes a module pointer to a media struct
 * Parameters:
 *	mod	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
reset_cluster_action(Module *mod)
{
	Module	*prodmod;

	prodmod = mod->sub;
	while (prodmod &&
		(prodmod->type == PRODUCT || prodmod->type == NULLPRODUCT)) {
		walklist(prodmod->info.prod->p_clusters,
		    _reset_cluster_action, (caddr_t)NO_ACTION_DEFINED);
		prodmod = prodmod->next;
	}
}

/*
 * mark_action()
 * Parameters:
 *	np	- node pointer
 *	data	-
 * Return:
 *	0
 * Status:
 *	private
 */
static int
mark_action(Node * np, caddr_t data)
{
	Modinfo *mi;

	mi = (Modinfo *)(np->data);
	mi->m_action = (Action)(data);
	while ((mi = next_inst(mi)) != NULL)
		mi->m_action = (Action)(data);

	return (0);
}

/*
 * _reset_cluster_action()
 * Parameters:
 *	np	- node pointer
 *	data	-
 * Return:
 *	0
 * Status:
 *	private
 */
static int
_reset_cluster_action(Node * np, caddr_t data)
{
	Module *mod;

	mod = (Module *)(np->data);
	mod->info.mod->m_action = (Action)(data);
	return (0);
}

/*
 * reset_instdir()
 * Parameters:
 *	np	- node pointer
 *	data	-
 * Return:
 *	0
 * Status:
 *	private
 */
/*ARGSUSED1*/
static int
reset_instdir(Node * np, caddr_t data)
{
	Modinfo *mi;

	mi = (Modinfo *)(np->data);
	if (mi->m_instdir) {
		free(mi->m_instdir);
		mi->m_instdir = NULL;
	}
	while ((mi = next_inst(mi)) != NULL) {
		if (mi->m_instdir) {
			free(mi->m_instdir);
			mi->m_instdir = NULL;
		}
	}
	return (0);
}

/*
 * generate string of the form:
 * /export/root/templates/<product>_<ver>/<pkg>_<pkgver>_<arch>
 */
static char *
genspooldir(Modinfo *mi)
{
	int	len;
	char	*cp;

	len = strlen(template_dir) +
			strlen(g_newproduct->p_name) +
			strlen(g_newproduct->p_version) +
			strlen(mi->m_pkgid) +
			strlen(mi->m_version) +
			strlen(mi->m_arch);
	len += 6;		/* miscelleneous delimeters in string */

	if (strchr(mi->m_arch, '.')) {
		cp = (char *)xmalloc((size_t)len);
		(void) snprintf(cp, (size_t)len, "%s/%s_%s/%s_%s_%s",
		    template_dir,
		    g_newproduct->p_name,
		    g_newproduct->p_version,
		    mi->m_pkgid, mi->m_version, mi->m_arch);
	} else {
		len += 5;   /* ".all" */
		cp = (char *)xmalloc((size_t)len);
		(void) snprintf(cp, (size_t)len, "%s/%s_%s/%s_%s_%s.all",
		    template_dir,
		    g_newproduct->p_name,
		    g_newproduct->p_version,
		    mi->m_pkgid, mi->m_version, mi->m_arch);
	}
	return (cp);
}

/*
 * set_alt_clsstat()
 * Parameters:
 *	selected	-
 *	mod		-
 * Return:
 *
 * Status:
 *	private
 */
static int
set_alt_clsstat(int selected, Module *mod)
{
int	toggles_needed;

	if (selected != PARTIALLY_SELECTED &&
	    mod->info.mod->m_status != PARTIALLY_SELECTED)
		if (selected != mod->info.mod->m_status)
			toggles_needed = 1;
		else
			toggles_needed = 0;
	else if (selected == PARTIALLY_SELECTED || selected == UNSELECTED)
		if (mod->info.mod->m_status == SELECTED ||
			(mod->info.mod->m_status == PARTIALLY_SELECTED &&
			partial_status(mod) == SELECTED))
			toggles_needed = 1;
		else
			toggles_needed = 0;
	else
		/*
		 * selected == SELECTED and
		 * mod_info->status == PARTIALLY_SELECTED
		 */
		toggles_needed = 2;

	if (toggles_needed == 2) {
		toggle_module(mod);
		if (mod->info.mod->m_status == PARTIALLY_SELECTED)
			toggle_module(mod);
	} else if (toggles_needed == 1)
		toggle_module(mod);

	return (toggles_needed);
}

/*
 * check_if_diskless()
 *	Check if it's a diskless install.
 * Parameters:
 *      none
 * Return:
 *	1 - If diskless_install
 * Status:
 *      private
 */
int
check_if_diskless(void) {

	if (diskless_install)
		return (1);
	else
		return (0);
}

/*
 * find_clients()
 * Parameters:
 *	none
 * Return:
 *
 * Status:
 *	private
 */
static struct client *
find_clients(void)
{
	char	file[MAXPATHLEN];
	char	line[MAXPATHLEN];
	char	rootdir[MAXPATHLEN + 1];
	DIR	*dirp;
	struct dirent	*dp;
	struct client	*client_ptr, *client_head;
	char	cname[MAXHOSTNAMELEN];
	FILE	*fp;

	client_head = NULL;

	(void) snprintf(file, MAXPATHLEN, "%s/export/root", get_rootdir());
	if ((dirp = opendir(file)) == (DIR *)NULL)
		return ((struct client *)NULL);

	while ((dp = readdir(dirp)) != (struct dirent *)0) {
		if (strcmp(dp->d_name, ".") == 0 ||
					strcmp(dp->d_name, "..") == 0 ||
					strcmp(dp->d_name, "templates") == 0)
			continue;

		(void) snprintf(file, MAXPATHLEN,
		    "%s/export/root/%s/var/sadm/install/contents",
		    get_rootdir(), dp->d_name);
		if (path_is_readable(file) != SUCCESS)
			continue;
		client_ptr = (struct client *)
			xmalloc((size_t)sizeof (struct client));
		(void) strcpy(client_ptr->client_name, dp->d_name);
		client_ptr->client_root = xmalloc((size_t)
		    strlen("/export/root/") + strlen(dp->d_name) + 1);
		(void) strcpy(client_ptr->client_root, "/export/root/");
		(void) strcat(client_ptr->client_root, dp->d_name);
		client_ptr->next_client = client_head;
		client_head = client_ptr;
	}
	(void) closedir(dirp);

	(void) upgrading_clients();
		/*
		 * Clones are just like clients.
		 * If upgrading clients in the future
		 * Find clone clients clone/Solaris_<version>/sun4[cdmu]
		 */

	(void) snprintf(file, MAXPATHLEN, "%s/etc/dfs/dfstab", get_rootdir());
	if ((fp = fopen(file, "r")) == NULL)
		return (client_head);

	/* check /etc/dfs/dfstab for any other clients */
	while (fgets(line, BUFSIZ, fp)) {
		if (sscanf(line, "share -F nfs -o rw=%*[^,],root="
					"%"STRINGIZE(MAXHOSTNAMELEN)"s "
					"%"STRINGIZE(MAXPATHLEN)"s",
						cname, rootdir) != 2)
			continue;

		if (cname == NULL || rootdir == NULL)
			continue;

		for (client_ptr = client_head; client_ptr; client_ptr =
						client_ptr->next_client) {
			if (streq(cname, client_ptr->client_name))
				break;
		}
		if (client_ptr)
			continue;

		(void) snprintf(file, MAXPATHLEN,
		    "%s/%s/var/sadm/install/contents",
		    get_rootdir(), rootdir);
		if (path_is_readable(file) != SUCCESS)
			continue;

		client_ptr = (struct client *)
			xmalloc((size_t)sizeof (struct client));
		(void) strcpy(client_ptr->client_name, cname);
		client_ptr->client_root = xstrdup(rootdir);
		client_ptr->next_client = client_head;
		client_head = client_ptr;
	}

	(void) fclose(fp);

	return (client_head);
}

/*
 * mark_required_metacluster()
 * Parameters:
 *	prodmod	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
mark_required_metacluster(Module * prodmod)
{
	Module *mod;

	mod = prodmod->sub;
	/*
	 * mod now points to the first cluster.  Find the
	 * required metacluster and mark in required in the
	 * new media structure.
	 */

	while (mod != NULL) {
		if (mod->type == METACLUSTER &&
			strcmp(mod->info.mod->m_pkgid,
			REQUIRED_METACLUSTER) == 0) {
			mark_required(mod);
			break;
		}
		mod = mod->next;
	}
}

/*
 * set_inst_dir()
 *	set the installation directory for the new package.
 *	media_mod:	the media module which heads the existing service or
 *			environment
 *	    mnew :	modinfo struct of new package,
 *	      mi :	modinfo struct of existing package that this package is
 *			replacing (may be NULL)
 * Parameters:
 *	media_mod	-
 *	mnew		-
 *	mi		-
 * Return:
 *	none
 */
static void
set_inst_dir(Module * media_mod, Modinfo * mnew, Modinfo * mi)
{
	char	buf[MAXPATHLEN];
	char	isabuf[ARCH_LENGTH];
	char	*cp;

	if (mnew->m_action == EXISTING_NO_ACTION)
		return;
	else if (mnew->m_action == TO_BE_SPOOLED)
		mnew->m_instdir = genspooldir(mnew);
	else if (mnew->m_action == TO_BE_PKGADDED ||
	    mnew->m_action == ADDED_BY_SHARED_ENV) {
		if (media_mod->info.media->med_type == INSTALLED) {
			/*
			 * If the basedir has changed between the old instance
			 * of the package and the new instance, use the basedir
			 * of the old instance unless the BASEDIR_CHANGE keyword
			 * was specified in the pkghistory file.  We normally
			 * preserve the basedir because the user could have
			 * manually specified a non-default one.
			 */
			if (mi && mi->m_basedir != NULL &&
			    !streq(mi->m_basedir, mnew->m_basedir) &&
			    (mi->m_pkg_hist == NULL ||
			    !mi->m_pkg_hist->basedir_change)) {
				/* use basedir of existing package */
				mnew->m_instdir = xstrdup(mi->m_basedir);
			} else {
				/* use basedir instead */
				mnew->m_instdir = NULL;
			}
		} else {		/* it's a service */
			(void) strcpy(isabuf, mnew->m_arch);
			cp = strchr(isabuf, '.');
			if (cp != NULL)
				*cp = '\0';
			if (media_mod->info.media->med_flags &
			    SPLIT_FROM_SERVER) {
				/*
				 * NOTICE: There is a bit of magic
				 * that is going on here. for post-KBI
				 * services there are no KVM type
				 * packages, but there is a small
				 * transition period were they may
				 * exist. So to fix this problem the
				 * use of the is_KBI_service routine
				 * is used to show if this is a KBI
				 * service or not. For post-KBI
				 * services there is no need for the
				 * special /export/exec/kvm directory,
				 * so the instdir should just be the
				 * base dir.
				 */
				if ((mnew->m_sunw_ptype == PTYPE_KVM &&
				    (!is_KBI_service(g_newproduct))) &&
				    strcmp(get_default_arch(),
					mnew->m_arch) != 0) {
					(void) snprintf(buf, MAXPATHLEN,
					    "/export/exec/kvm/%s_%s_%s",
					    g_newproduct->p_name,
					    g_newproduct->p_version,
					    mnew->m_arch);
					if (strcmp(mnew->m_basedir, "/") != 0)
						(void) strcat(buf,
						    mnew->m_basedir);
					mnew->m_instdir = xstrdup(buf);
				} else if (mnew->m_sunw_ptype == PTYPE_KVM &&
				    is_KBI_service(g_newproduct) &&
				    !supports_arch(get_default_arch(),
				    isabuf)) {
					(void) snprintf(buf, MAXPATHLEN,
					    "/export/exec/%s_%s_%s.all",
					    g_newproduct->p_name,
					    g_newproduct->p_version,
					    isabuf);
					if (strcmp(mnew->m_basedir, "/") != 0)
						(void) strcat(buf,
						    mnew->m_basedir);
					mnew->m_instdir = xstrdup(buf);
				} else if ((mnew->m_sunw_ptype == PTYPE_USR ||
				    mnew->m_sunw_ptype == PTYPE_OW) &&
				    !supports_arch(get_default_arch(),
					mnew->m_arch)) {
					(void) snprintf(buf, MAXPATHLEN,
					    "/export/exec/%s_%s_%s",
					    g_newproduct->p_name,
					    g_newproduct->p_version,
					    mnew->m_expand_arch);
					if (strcmp(mnew->m_basedir, "/") != 0)
						(void) strcat(buf,
						    mnew->m_basedir);
					mnew->m_instdir = xstrdup(buf);
				} else  /* use basedir */
					mnew->m_instdir = NULL;
			} else {
				if (mnew->m_sunw_ptype == PTYPE_KVM &&
				    !is_KBI_service(g_newproduct))
					(void) snprintf(buf, MAXPATHLEN,
					    "/usr.kvm_%s", mnew->m_arch);
				else if (mnew->m_sunw_ptype == PTYPE_KVM &&
				    is_KBI_service(g_newproduct))
					(void) snprintf(buf, MAXPATHLEN,
					    "/usr_%s.all", isabuf);
				else if (mnew->m_sunw_ptype == PTYPE_USR ||
				    mnew->m_sunw_ptype == PTYPE_OW)
					(void) snprintf(buf, MAXPATHLEN,
					    "/usr_%s.all", mnew->m_arch);
				else   /* opt or shared */
					(void) snprintf(buf, MAXPATHLEN,
					    "/export/%s_%s",
					    g_newproduct->p_name,
					    g_newproduct->p_version);
				if (strcmp(mnew->m_basedir, "/") != 0)
					(void) strcat(buf, mnew->m_basedir);
				mnew->m_instdir = xstrdup(buf);

			}
		}
	}
}

/*
 * cluster_match()
 * Parameters:
 *	cls_list	-
 *	media_mod	-
 * Return:
 *
 * Status:
 *	private
 */
static int
cluster_match(char *cls_list, Module *media_mod)
{
	char	*cp, *p;
	Module	*mod;

	if (cls_list == NULL)
		return (0);

	for (mod = media_mod->sub->sub; mod != NULL; mod = mod->next)
		if (mod->type == METACLUSTER)
			break;
	if (mod == NULL)
		return (0);

	cp = cls_list;
	while ((p = split_name(&cp)) != NULL) {
		/*
		 * If wildcard value ALL is present in the REMOVE_FROM_CLUSTER
		 * list return 1 to remove from the upgrade
		 */
		if (strcmp(p, WILDCARD_METACLUSTER) == 0)
			return (1);
		if (strcmp(p, mod->info.mod->m_pkgid) == 0)
			return (1);
	}
	return (0);
}

/*
 * spool_selected_arches()
 * Parameters:
 *	id	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
spool_selected_arches(char *id)
{
	Node	*node;
	Modinfo	*mi;

	node = findnode(g_newproduct->p_packages, id);
	if (node) {
		mi = (Modinfo *)(node->data);
		if (mi->m_shared != NULLPKG && is_arch_selected(mi->m_arch)) {
			mi->m_status = REQUIRED;
			mi->m_action = TO_BE_SPOOLED;
			mi->m_instdir = genspooldir(mi);
		}
		while ((node = mi->m_instances) != NULL) {
			mi = (Modinfo *)(node->data);
			if (mi->m_shared != NULLPKG &&
				is_arch_selected(mi->m_arch)) {
				mi->m_status = REQUIRED;
				mi->m_action = TO_BE_SPOOLED;
				mi->m_instdir = genspooldir(mi);
			}
		}
	}
}

/*
 * is_arch_selected()
 * Parameters:
 *	arch	-
 * Return:
 *
 * Status:
 *	private
 */
static int
is_arch_selected(char *arch)
{
	Arch *ap;
	int ret;

	for (ap = g_newproduct->p_arches; ap != NULL; ap = ap->a_next)
		if (ap->a_selected) {
			ret = compatible_arch(arch, ap->a_arch);
			if (ret == ARCH_MATCH || ret == ARCH_MORE_SPECIFIC)
				return (1);
		}
	return (0);
}

/*
 * is_arch_supported()
 * Parameters:
 *	arch	-
 * Return:
 *
 * Status:
 *	private
 */
static int
is_arch_supported(char *arch)
{
	Arch *ap;
	int ret;

	for (ap = g_newproduct->p_arches; ap != NULL; ap = ap->a_next) {
		ret = compatible_arch(arch, ap->a_arch);
		if (ret == ARCH_MATCH || ret == ARCH_MORE_SPECIFIC)
				return (1);
	}
	return (0);
}

static void
update_patch_status(Product *prod)
{
	struct patch *p;
	struct patchpkg *ppkg;

	for (p = prod->p_patches; p != NULL; p = p->next) {
		for (ppkg = p->patchpkgs; ppkg != NULL; ppkg = ppkg->next) {
			if (ppkg->pkgmod->m_patchof) {
				if (ppkg->pkgmod->m_patchof->m_action ==
				    TO_BE_PRESERVED)
					break;
			} else
				if (ppkg->pkgmod->m_action == TO_BE_PRESERVED)
					break;
		}
		/*
		 *  If any of the patch packages are for packages that
		 *  are being preserved, the patch as a whole will not
		 *  be removed.
		 */
		if (ppkg != NULL)
			p->removed = 0;
		else
			p->removed = 1;
	}
}

static void
diff_rev(Modinfo *mi, Modinfo *mnew)
{
	if (g_sw_diffrev)
		free_diff_rev(g_sw_diffrev);
	g_sw_diffrev = (SW_diffrev *) xcalloc((size_t)sizeof (SW_diffrev));
	g_sw_diffrev->sw_diffrev_pkg = xstrdup(mi->m_pkgid);
	g_sw_diffrev->sw_diffrev_arch = xstrdup(mi->m_arch);
	g_sw_diffrev->sw_diffrev_curver = xstrdup(mi->m_version);
	if (mnew && mnew->m_version)
		g_sw_diffrev->sw_diffrev_newver = xstrdup(mnew->m_version);
	else
		g_sw_diffrev->sw_diffrev_newver = xstrdup("");
}

/*
 * set_instances_action()
 *	This private function runs all of the instances of a package and
 *	sets the instance's action code. Primarly this function is used to
 *	remove extra instances of a package.
 *
 * Parameters:
 *	np	- node pointer
 *	data	- action code
 * Return:
 *	0
 * Status:
 *	private
 */
static void
set_instances_action(Modinfo *mi, Action data)
{
	Modinfo *imi;

	imi = mi;
	while ((imi = next_inst(imi)) != NULL)
		if (mi->m_arch != NULL && imi->m_arch != NULL &&
		    imi->m_shared != SPOOLED_NOTDUP &&
		    streq(mi->m_arch, imi->m_arch)) {
			imi->m_action = data;
			imi->m_flags |= DO_PKGRM;
		}
}

/*
 * set_patch_action()
 * Parameters:
 *	np	-
 *	data	-
 * Return:
 * Status:
 *	private
 */
static int
	/* LINTED [missing parameter ok] */
set_patch_action(Node * np, caddr_t data)
{
	Modinfo	*mi;

	mi = (Modinfo *)(np->data);
	_set_patch_action(mi);
	while ((mi = next_inst(mi)) != NULL)
		_set_patch_action(mi);
	return (0);
}

static void
_set_patch_action(Modinfo *mi)
{
	Modinfo *mip;
	Action	action;

	if (mi->m_next_patch) {
		if (mi->m_action == TO_BE_REPLACED)
			action = TO_BE_REMOVED;
		else
			action = mi->m_action;

		for (mip = next_patch(mi); mip != NULL; mip = next_patch(mip))
			mip->m_action = action;
	}
}

int
set_action_code_mode(ActionCodeMode mode)
{
	Module	*mediamod;

	if (mode == action_mode)
		return (SUCCESS);
	action_mode = mode;

	mediamod = get_localmedia();
	(void) load_view(g_newproductmod, mediamod);
	reprocess_module_tree(mediamod, mediamod->sub);
	mark_arch(g_newproductmod);
	sync_l10n(g_newproductmod);
	update_patch_status(mediamod->sub->info.prod);

	/* update the action codes in every other view too */

	mediamod = get_media_head();
	while (mediamod != NULL) {
		if ((mediamod->info.media->med_type == INSTALLED_SVC ||
		    mediamod->info.media->med_type == INSTALLED) &&
		    mediamod != get_localmedia() &&
		    has_view(g_newproductmod, mediamod) == SUCCESS) {
			(void) load_view(g_newproductmod, mediamod);
			reprocess_module_tree(mediamod, mediamod->sub);
			/* if a client */
			if (mediamod->info.media->med_type == INSTALLED &&
			    mediamod->info.media->med_zonename == NULL) {
				unreq_nonroot(g_newproductmod);
				set_primary_arch(g_newproductmod);
			} else {
				mark_arch(g_newproductmod);
			}
			sync_l10n(g_newproductmod);
			update_patch_status(mediamod->sub->info.prod);
		}
		mediamod = mediamod->next;
	}
	(void) load_view(g_newproductmod, get_localmedia());
	return (SUCCESS);
}

/*
 * resolve_references()
 *	used when non-global zone data is read from pipe:
 *	- for cross-referenced data, updates pointers to point to new data
 *	- frees unneeded (old or redundant) data
 * Parameters:
 *	prod	- product
 * Status:
 *	private
 */
static void
resolve_references(Module *prod)
{
	Modinfo		*mi, *mii, *mip, *real_mi;
	Module		*loc, *pkgmod, *real_comp, *comp, *next_comp,
			*clust_pkg, *next_clust_pkg, *real_clst, *clst;
	List		*plist, *clist;
	Node		*n, *real_node;
	L10N		*l10n;
	PkgsLocalized	*pl;
	struct patch	*pat;
	struct patchpkg	*ppkg;
	int		found;

	plist = prod->info.prod->p_packages;
	clist = prod->info.prod->p_clusters;

	if (!plist || !clist)
		return;

	/* Traverse the Product's p_package list */
	for (n = plist->list->next; n && n != plist->list; n = n->next) {
		mi = (Modinfo *)n->data;

		/* Traverse each p_package's m_l10n */
		for (l10n = mi->m_l10n; l10n; l10n = l10n->l10n_next) {
			if (l10n->l10n_package) {

				real_node =
				    findnode(prod->info.prod->p_packages,
				    l10n->l10n_package->m_pkgid);

				if (real_node) {
					free(l10n->l10n_package->m_pkgid);
					free(l10n->l10n_package);
					l10n->l10n_package =
					    (Modinfo *)real_node->data;
				}
			}
		}

		/* Traverse each p_package's m_pkgs_lclzd */
		for (pl = mi->m_pkgs_lclzd; pl; pl = pl->next) {
			if (pl->pkg_lclzd) {
				real_node =
				    findnode(prod->info.prod->p_packages,
				    pl->pkg_lclzd->m_pkgid);

				if (real_node) {
					free(pl->pkg_lclzd->m_pkgid);
					free(pl->pkg_lclzd);
					pl->pkg_lclzd =
					    (Modinfo *)real_node->data;
				}
			}
		}

		/* Traverse each p_package's m_instance list */
		for (mii = mi; mii; mii = next_inst(mii)) {
			/*
			 * Traverse each p_package's m_instance's
			 * m_next_patch list
			 */
			if (mii->m_next_patch) {
				mip = (Modinfo *) (mii->m_next_patch)->data;
				for (; mip; mip = next_patch(mip)) {
					/*
					 * Set each next_patch's m_patchof to
					 * the m_instance it falls under
					 */
					free(mip->m_patchof->m_pkgid);
					free(mip->m_patchof);
					mip->m_patchof = mii;
				}
			}
		}
	}

	/*
	 * Product's p_clusters list
	 */
	for (n = clist->list->next; n && n != clist->list; n = n->next) {
		clst = (Module *) n->data;
		if (clst->type == CLUSTER) {
			for (pkgmod = clst->sub; pkgmod;
			    pkgmod = pkgmod->next) {
				if ((real_node = findnode(plist,
				    pkgmod->info.mod->m_pkgid)) != NULL) {
					free_modinfo(pkgmod->info.mod);
					pkgmod->info.mod =
					    (Modinfo *)real_node->data;
				}
			}
		} else if (clst->type == METACLUSTER) {
			for (comp = clst->sub; comp; comp = next_comp) {
				next_comp = comp->next;
				if (comp->type == CLUSTER) {
					if ((real_node = findnode(clist,
					    comp->info.mod->m_pkgid)) != NULL) {
						real_comp =
						    (Module *)real_node->data;

						if (comp == clst->sub) {
							clst->sub = real_comp;
						}
						real_comp->next = comp->next;
						real_comp->prev = comp->prev;
						real_comp->head = clst->sub;
						real_comp->parent =
						    comp->parent;
						if (comp->prev)
							comp->prev->next =
							    real_comp;
						if (comp->next)
							comp->next->prev =
							    real_comp;

						/* free comp tree */
						for (clust_pkg = comp->sub;
						    clust_pkg;
						clust_pkg = next_clust_pkg) {
							next_clust_pkg =
							    clust_pkg->next;
							free_modinfo(
							clust_pkg->info.mod);
							free(clust_pkg);
						}
						free_modinfo(comp->info.mod);
						free(comp);
					}
				} else if (comp->type == PACKAGE) {
					if ((real_node = findnode(plist,
					    comp->info.mod->m_pkgid)) != NULL) {
						free_modinfo(comp->info.mod);
						comp->info.mod =
						    (Modinfo *)real_node->data;
					}
				}
			}
		}
	}


	/*
	 * Product's p_patches list
	 *
	 * Find the real pkg modinfo structure which is in
	 * a pacakge's next_patch or a next_patch of an
	 * instance of the package.
	 *
	 * Product
	 *   |
	 *   |__>p_package -> p_package -> p_package -> ...
	 *	    |
	 *	    |__> m_next_patch -> m_next_patch -> ...
	 *	    |
	 *	    |____> m_next_instance -> m_next_instance -> ...
	 *		    |
	 *		    |__> m_next_patch -> m_next_patch -> ...
	 *
	 */
	for (pat = prod->info.prod->p_patches; pat; pat = pat->next) {
		for (ppkg = pat->patchpkgs; ppkg && ppkg->pkgmod;
		    ppkg = ppkg->next) {

			/*
			 * Okay found a non-NULL ppkg->pkgmod, now lets
			 * look for the real pkg modinfo
			 */

			found = 0;

			/* Look in p_package list */
			for (n = plist->list->next; n && n != plist->list;
			    n = n->next) {
				if (found == 1)
					break;

				mi = (Modinfo *)n->data;

				/* Look in each p_package's m_next_patch list */
				for (mip = mi; mip; mip = next_patch(mip)) {
					if (found == 1)
						break;

					if (streq(mip->m_pkgid,
					    ppkg->pkgmod->m_pkgid)) {

						/* Found it */
						free(ppkg->pkgmod->m_pkgid);
						free(ppkg->pkgmod);
						ppkg->pkgmod = mip;
						found = 1;
					}
				}

				/*
				 * Look in each p_package's m_next_instance
				 * m_next_patch list.
				 */
				while (mi = next_inst(mi)) {
					if (found == 1)
						break;

					for (mip = mi; mip;
					    mip = next_patch(mip)) {
						if (found == 1)
							break;

						if (streq(mip->m_pkgid,
						    ppkg->pkgmod->m_pkgid)) {

						    /* Found it */
						    free(ppkg->pkgmod->m_pkgid);
						    free(ppkg->pkgmod);
						    ppkg->pkgmod = mip;
						    found = 1;
						}
					}
				}
			}
		}
	}

	/* Product's p_locale list */
	for (loc = prod->info.prod->p_locale; loc; loc = loc->next) {

		/* Set the locale's parent module */
		loc->parent = prod;

		/*
		 * Traverse the locale's sub modules (packages) and find
		 * the real pkg modinfo from the p_packages list.
		 */
		for (pkgmod = loc->sub; pkgmod; pkgmod = pkgmod->next) {
			if ((real_node = findnode(plist,
			    pkgmod->info.mod->m_pkgid)) != NULL) {
				free_modinfo(pkgmod->info.mod);
				pkgmod->info.mod = (Modinfo *)real_node->data;
			}
		}
	}

	/*
	 * Product's sub modules are the Metacluster that's installed,
	 * and also other package clusters or packages outside of Metacluster
	 * that may be installed.  These modules live in either the p_clusters
	 * list or the p_packages list, so we find them and set them
	 * accordingly.
	 */
	for (clst = prod->sub; clst; clst = clst->next) {

		/*
		 * If the sub module is of type PACKAGE then get the real data
		 * from the p_packages list, otherwise its a METACLUSTER or a
		 * CLUSTER so get it from the p_clusters list.
		 */
		if (clst->type == PACKAGE) {
			if ((real_node =
			    findnode(plist, clst->info.mod->m_pkgid)) != NULL) {
				real_mi = (Modinfo *)real_node->data;
				free_modinfo(clst->info.mod);
				clst->info.mod = real_mi;
			}
		} else if ((real_node =
		    findnode(clist, clst->info.mod->m_pkgid)) != NULL) {
			real_clst = (Module *)real_node->data;
			if (clst == prod->sub)
				prod->sub = real_clst;
			real_clst->next = clst->next;
			real_clst->prev = clst->prev;
			real_clst->head = prod->sub;
			real_clst->parent = clst->parent;
			if (clst->prev)
				clst->prev->next = real_clst;
			if (clst->next)
				clst->next->prev = real_clst;

			/*
			 * Free the METACLUSTER or CLUSTER's sub trees.
			 */
			if (clst->type == METACLUSTER) {
				for (comp = clst->sub; comp;
				    comp = next_comp) {
					next_comp = comp->next;
					if (comp->type == CLUSTER) {
						for (clust_pkg = comp->sub;
						    clust_pkg; clust_pkg =
						    next_clust_pkg) {
							next_clust_pkg =
							    clust_pkg->next;
							free_modinfo(
							clust_pkg->info.mod);
							free(clust_pkg);
						}
					}
					free_modinfo(comp->info.mod);
					free(comp);
				}
			} else if (clst->type == CLUSTER) {
				for (clust_pkg = clst->sub; clust_pkg;
				    clust_pkg = next_clust_pkg) {
					next_clust_pkg = clust_pkg->next;
					free_modinfo(clust_pkg->info.mod);
					free(clust_pkg);
				}
			}

			free_modinfo(clst->info.mod);
			free(clst);
			clst = real_clst;
		}
	}
}
