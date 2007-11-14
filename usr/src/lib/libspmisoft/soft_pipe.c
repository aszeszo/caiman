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

#pragma ident	"@(#)soft_pipe.c	1.2	07/11/08 SMI"

#include "spmisoft_lib.h"
#include "sw_pipe.h"

#include <dirent.h>
#include <string.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/stat.h>
#include <locale.h>
#include <stdlib.h>

/*
 * STRNCMPC - perform strncmp with literal string
 * if b is a prefix of a, return 0
 * parameters:
 *	a - char *
 *	b - char string literal
 * b must be a literal string
 * automatically provides length of string literal to strncmp
 */
#define	STRNCMPC(a, b) strncmp((a), b, sizeof (b) - 1)

extern int is_child_zone_context;

/* Public Function Prototypes */
char *fgetspipe(char *, int bufsiz, FILE *);

/* Library Function Prototypes */
Module		*read_module_from_pipe(FILE *);
Modinfo		*read_modinfo_from_pipe(FILE *);
Media		*read_media_from_pipe(FILE *);
Product		*read_product_from_pipe(FILE *);
Geo		*read_geo_from_pipe(FILE *);
Locale		*read_locale_from_pipe(FILE *);
Category	*read_category_from_pipe(FILE *);
L10N		*read_l10n_from_pipe(FILE *);
PkgsLocalized	*read_pkgslocalized_from_pipe(FILE *);
Node		*read_modinfo_node_from_pipe(FILE *, boolean_t);
Node		*read_module_node_from_pipe(FILE *, boolean_t);
Depend		*read_depend_from_pipe(FILE *);
File		**read_filepp_from_pipe(FILE *);
File		*read_file_from_pipe(FILE *);
struct pkg_hist	*read_pkg_hist_from_pipe(FILE *);
struct filediff	*read_filediff_from_pipe(FILE *, boolean_t);
struct patch_num	*read_patch_num_from_pipe(FILE *);
StringList	*read_stringlist_from_pipe(FILE *);
ContentsRecord	*read_contentsrecord_from_pipe(FILE *);
int		read_contentsbrkdn_from_pipe(FILE *, ContentsBrkdn *);
char		**read_charpp_from_pipe(FILE *);
Arch		*read_arch_from_pipe(FILE *);
List		*read_modinfo_list_from_pipe(FILE *);
List		*read_module_list_from_pipe(FILE *);
struct pkg_info	*read_pkg_info_from_pipe(FILE *);
SW_config	*read_sw_config_from_pipe(FILE *);
HW_config	*read_hw_config_from_pipe(FILE *);
PlatGroup	*read_platgroup_from_pipe(FILE *);
Platform	*read_platform_from_pipe(FILE *);
struct patch	*read_patch_from_pipe(FILE *);
struct patchpkg	*read_patchpkg_from_pipe(FILE *);
int		read_filediff_owning_pkg_from_pipe(FILE *, Module *);

int		write_module_to_pipe(FILE *, Module *, boolean_t);
int		write_modinfo_to_pipe(FILE *, Modinfo *);
int		write_media_to_pipe(FILE *, Media *);
int		write_product_to_pipe(FILE *, Product *);
int		write_geo_to_pipe(FILE *, Geo *);
int		write_locale_to_pipe(FILE *, Locale *);
int		write_category_to_pipe(FILE *, Category *);
int		write_l10n_to_pipe(FILE *, L10N *);
int		write_pkgslocalized_to_pipe(FILE *, PkgsLocalized *);
int		write_modinfo_node_to_pipe(FILE *, Node *, boolean_t);
int		write_module_node_to_pipe(FILE *, Node *, boolean_t, boolean_t);
int		write_depend_to_pipe(FILE *, Depend *);
int		write_filepp_to_pipe(FILE *, File **);
int		write_file_to_pipe(FILE *, File *);
int		write_pkg_hist_to_pipe(FILE *, struct pkg_hist *);
int		write_filediff_to_pipe(FILE *, struct filediff *, boolean_t);
int		write_patch_num_to_pipe(FILE *, struct patch_num *);
int		write_stringlist_to_pipe(FILE *, StringList *);
int		write_contentsrecord_to_pipe(FILE *, ContentsRecord *);
int		write_contentsbrkdn_to_pipe(FILE *, ContentsBrkdn *);
int		write_charpp_to_pipe(FILE *, char **);
int		write_arch_to_pipe(FILE *, Arch *);
int		write_modinfo_list_to_pipe(FILE *, List *);
int		write_module_list_to_pipe(FILE *, List *);
int		write_pkg_info_to_pipe(FILE *, struct pkg_info *);
int		write_sw_config_to_pipe(FILE *, SW_config *);
int		write_hw_config_to_pipe(FILE *, HW_config *);
int		write_platgroup_to_pipe(FILE *, PlatGroup *);
int		write_platform_to_pipe(FILE *, Platform *);
int		write_patch_to_pipe(FILE *, struct patch *);
int		write_patchpkg_to_pipe(FILE *, struct patchpkg *);
int		write_filediff_owning_pkg_to_pipe(FILE *, struct filediff *);

void		print_space_usage(FILE *, char *, FSspace **);
int		read_real_modified_list_from_pipe(FILE *, Module *);
int		write_real_modified_list_to_pipe(FILE *);

/* Local Function Protoyptes */

/* Local Variables */


/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */



/* ******************************************************************** */
/*			LIBRARY SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * read_module_from_pipe
 *	Read a Module structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read Module from
 * Returns:
 *	Module *	- Pointer to Module read from the file stream.
 *			The Module returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Module from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Module *
read_module_from_pipe(FILE *fp)
{
	Module		*mod, *child;
	char		buf[BUFSIZ];
	int		err = 0;

	mod = (Module *)xcalloc(sizeof (Module));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "type=") == 0) {
			mod->type = atoi(get_value(buf, '='));
			switch (mod->type) {
			case PACKAGE:
				if ((mod->info.mod =
				    read_modinfo_from_pipe(fp)) == NULL) {
					err = SP_PIPE_ERR_READ_MODINFO;
					goto done;
				}
				break;
			case PRODUCT:
			case NULLPRODUCT:
				if ((mod->info.prod =
				    read_product_from_pipe(fp)) == NULL) {
					err = SP_PIPE_ERR_READ_PRODUCT;
					goto done;
				}
				if (mod->info.prod->p_categories)
					mod->info.prod->p_categories->parent =
					    mod;
				break;
			case MEDIA:
				if ((mod->info.media =
				    read_media_from_pipe(fp)) == NULL) {
					err = SP_PIPE_ERR_READ_MEDIA;
					goto done;
				}
				break;
			case CLUSTER:
			case METACLUSTER:
			case UNBUNDLED_4X:
				if ((mod->info.mod =
				    read_modinfo_from_pipe(fp)) == NULL) {
					err = SP_PIPE_ERR_READ_MODINFO;
					goto done;
				}
				break;
			case CATEGORY:
				if ((mod->info.cat =
				    read_category_from_pipe(fp)) == NULL) {
					err = SP_PIPE_ERR_READ_CATEGORY;
					goto done;
				}
				break;
			case LOCALE:
				if ((mod->info.locale =
				    read_locale_from_pipe(fp)) == NULL) {
					err = SP_PIPE_ERR_READ_LOCALE;
					goto done;
				}
				break;
			case GEO:
				if ((mod->info.geo =
				    read_geo_from_pipe(fp)) == NULL) {
					err = SP_PIPE_ERR_READ_GEO;
					goto done;
				}
				break;
			default:
				/* Other mod types not implemented */
				break;
			}
		} else if (strcmp(buf, "MODULE_SUB") == 0) {

			/*
			 * If this is an installed Product module
			 * (type == NULLPRODUCT), read in blank sub module's.
			 * The caller of this function will have to resolve
			 * the real pointers to the sub modules, which live
			 * in this Product's p_clusters list.
			 */
			if (mod->type == NULLPRODUCT) {
				mod->sub = (Module *)xcalloc(sizeof (Module));
				while (fgets(buf, BUFSIZ, fp) != NULL) {
					buf[strlen(buf) - 1] = '\0';
					if (STRNCMPC(buf, "type=") == 0) {
						mod->sub->type =
						    atoi(get_value(buf, '='));
					} else if (STRNCMPC(buf, "m_pkgid=")
					    == 0) {
						mod->sub->info.mod =
						    (Modinfo *)xcalloc(
						    sizeof (Modinfo));
						mod->sub->info.mod->m_pkgid =
						    xstrdup(get_value(buf,
						    '='));
					} else if (strcmp(buf, "END_MODULE")
					    == 0) {
						break;
					} else {
						err = SP_PIPE_ERR_READ_MODULE;
						goto done;
					}
				}
			} else {
				if ((mod->sub = read_module_from_pipe(fp)) ==
				    NULL) {
					err = SP_PIPE_ERR_READ_MODULE;
					break;
				}
			}
			mod->sub->parent = mod;
			mod->sub->head = mod->sub;

			child = mod->sub;

			/* Read in the sub's peers */
			while (fgets(buf, BUFSIZ, fp) != NULL) {
				buf[strlen(buf) - 1] = '\0';
				if (strcmp(buf, "MODULE_SUB_NEXT") == 0) {

				    if (mod->type == NULLPRODUCT) {
					child->next = (Module *)xcalloc(
					    sizeof (Module));
					while (fgets(buf, BUFSIZ, fp) != NULL) {
					buf[strlen(buf) - 1] = '\0';
					if (STRNCMPC(buf, "type=")
					    == 0) {
						child->next->type =
						    atoi(get_value(buf,
						    '='));
					} else if (STRNCMPC(buf, "m_pkgid=")
					    == 0) {
						child->next->info.mod =
						    (Modinfo *)xcalloc(
						    sizeof (Modinfo));
						child->next->info.mod->m_pkgid =
						    xstrdup(get_value(buf,
							'='));
					    } else if (strcmp(buf, "END_MODULE")
						== 0) {
						break;
					    } else {
						err =
						    SP_PIPE_ERR_READ_MODULE;
						goto done;
					    }
					}
				    } else {
					if ((child->next =
					    read_module_from_pipe(fp))
					    == NULL) {
					    err = SP_PIPE_ERR_READ_MODULE;
					    break;
					}
				    }
				    child->next->prev = child;
				    child->next->head = child->head;
				    child->next->parent = child->parent;
				    child = child->next;

				} else if (strcmp(buf, "END_MODULE") == 0) {
					goto done;
				} else {
					/* NOT SUPPOSED TO HAPPEN */
					err = SP_PIPE_ERR_READ_INVALID_LINE;
					goto done;
				}
			}

		} else if (strcmp(buf, "END_MODULE") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

done:
	if (err != 0) {
		free_module(mod);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading module: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (mod);
}

/*
 * read_modinfo_from_pipe
 *	Read a Modinfo structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read Modinfo from
 * Returns:
 *	Modinfo *	- Pointer to Modinfo read from the file stream.
 *			The Modinfo returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Modinfo from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Modinfo *
read_modinfo_from_pipe(FILE *fp)
{
	Modinfo		*mod;
	Modinfo		*mi;
	int		i;
	int		err = 0;
	struct filediff	*f;
	char		buf[BUFSIZ];

	mod = (Modinfo *)xcalloc(sizeof (Modinfo));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "m_order=") == 0) {
			mod->m_order = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_status=") == 0) {
			mod->m_status = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_shared=") == 0) {
			mod->m_shared = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_action=") == 0) {
			mod->m_action = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_flags=") == 0) {
			mod->m_flags = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_refcnt=") == 0) {
			mod->m_refcnt = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_sunw_ptype=") == 0) {
			mod->m_sunw_ptype = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_pkgid=") == 0) {
			mod->m_pkgid = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_pkginst=") == 0) {
			mod->m_pkginst = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_pkg_dir=") == 0) {
			mod->m_pkg_dir = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_name=") == 0) {
			mod->m_name = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_vendor=") == 0) {
			mod->m_vendor = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_version=") == 0) {
			mod->m_version = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_prodname=") == 0) {
			mod->m_prodname = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_prodvers=") == 0) {
			mod->m_prodvers = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_arch=") == 0) {
			mod->m_arch = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_expand_arch=") == 0) {
			mod->m_expand_arch = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_desc=") == 0) {
			mod->m_desc = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_category=") == 0) {
			mod->m_category = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_instdate=") == 0) {
			mod->m_instdate = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_patchid=") == 0) {
			mod->m_patchid = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_locale=") == 0) {
			mod->m_locale = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_l10n_pkglist=") == 0) {
			mod->m_l10n_pkglist = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "MODINFO_M_L10N") == 0) {
			if ((mod->m_l10n = read_l10n_from_pipe(fp)) == NULL) {
				return (NULL);
			}
		} else if (strcmp(buf, "MODINFO_M_PKGS_LCLZD") == 0) {
			if ((mod->m_pkgs_lclzd =
			    read_pkgslocalized_from_pipe(fp)) == NULL) {
				return (NULL);
			}
		} else if (strcmp(buf, "MODINFO_M_INSTANCES") == 0) {
			if ((mod->m_instances =
			    read_modinfo_node_from_pipe(fp, B_TRUE)) == NULL) {
				err = SP_PIPE_ERR_READ_MODINFO_NODE;
				break;
			}
		} else if (strcmp(buf, "MODINFO_M_NEXT_PATCH") == 0) {
			if ((mod->m_next_patch =
			    read_modinfo_node_from_pipe(fp, B_TRUE)) == NULL) {
				err = SP_PIPE_ERR_READ_MODINFO_NODE;
				break;
			}
		} else if (STRNCMPC(buf, "m_patchof=") == 0) {
			/*
			 * Create a blank Modinfo with just the m_pkgid
			 * filled in.  The caller who's reading this
			 * modinfo needs to find it in the Product's
			 * p_package list to set the pointer accordingly.
			 */
			mi = (Modinfo *)xcalloc(sizeof (Modinfo));
			mi->m_pkgid = xstrdup(get_value(buf, '='));

			mod->m_patchof = mi;

		} else if (strcmp(buf, "MODINFO_M_PDEPENDS") == 0) {
			if ((mod->m_pdepends =
			    read_depend_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_DEPEND;
				break;
			}
		} else if (strcmp(buf, "MODINFO_M_RDEPENDS") == 0) {
			if ((mod->m_rdepends =
			    read_depend_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_DEPEND;
				break;
			}
		} else if (strcmp(buf, "MODINFO_M_IDEPENDS") == 0) {
			if ((mod->m_idepends =
			    read_depend_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_DEPEND;
				break;
			}
		} else if (strcmp(buf, "MODINFO_M_TEXT") == 0) {
			if ((mod->m_text = read_filepp_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_FILEPP;
				break;
			}
		} else if (strcmp(buf, "MODINFO_M_DEMO") == 0) {
			if ((mod->m_demo = read_filepp_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_FILEPP;
				break;
			}
		} else if (strcmp(buf, "MODINFO_M_INSTALL") == 0) {
			if ((mod->m_install = read_file_from_pipe(fp)) ==
			    NULL) {
				err = SP_PIPE_ERR_READ_FILE;
				break;
			}
		} else if (strcmp(buf, "MODINFO_M_ICON") == 0) {
			if ((mod->m_icon = read_file_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_FILE;
				break;
			}
		} else if (STRNCMPC(buf, "m_basedir=") == 0) {
			mod->m_basedir = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "m_instdir=") == 0) {
			mod->m_instdir = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "MODINFO_M_PKG_HIST") == 0) {
			if ((mod->m_pkg_hist =
			    read_pkg_hist_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PKG_HIST;
				break;
			}
		} else if (STRNCMPC(buf, "m_spooled_size=") == 0) {
			if (sscanf(get_value(buf, '='), "%ld",
			    &(mod->m_spooled_size)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "m_pkgovhd_size=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(mod->m_pkgovhd_size)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (strcmp(buf, "MODINFO_M_DEFLT_FS_ARRAY") == 0) {
			for (i = 0; i < N_LOCAL_FS; i++) {
				if (fgets(buf, BUFSIZ, fp) == NULL) {
					err = SP_PIPE_ERR_READ_INVALID_LINE;
					break;
				}
				if (STRNCMPC(buf, "m_deflt_fs=") == 0) {
					if (sscanf(get_value(buf, '='), "%ld",
					    &(mod->m_deflt_fs[i])) != 1) {
						err =
						SP_PIPE_ERR_READ_SSCANF_FAILED;
						break;
					}
				} else {
					/* NOT SUPPOSED TO HAPPEN */
					err = SP_PIPE_ERR_READ_INVALID_LINE;
					break;
				}
			}
			if (fgets(buf, BUFSIZ, fp) == NULL) {
				err = SP_PIPE_ERR_READ_INVALID_LINE;
					break;
			} else {
				buf[strlen(buf) - 1] = '\0';
				if (strcmp(buf, "END_MODINFO_M_DEFLT_FS_ARRAY")
				    != 0) {
					err = SP_PIPE_ERR_READ_INVALID_LINE;
					break;
				}
			}
		} else if (strcmp(buf, "MODINFO_M_FILEDIFF") == 0) {
			if ((mod->m_filediff =
			    read_filediff_from_pipe(fp, B_TRUE)) == NULL) {
				err = SP_PIPE_ERR_READ_FILEDIFF;
				break;
			}
			/* set all filediffs' owning_pkg to this modinfo */
			for (f = mod->m_filediff; f != NULL; f = f->diff_next) {
				f->owning_pkg = mod;
			}
		} else if (strcmp(buf, "MODINFO_M_NEWARCH_PATCHES") == 0) {
			if ((mod->m_newarch_patches =
			    read_patch_num_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PATCH_NUM;
				break;
			}
		} else if (strcmp(buf, "MODINFO_M_LOC_STRLIST") == 0) {
			if ((mod->m_loc_strlist =
			    read_stringlist_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_STRINGLIST;
				break;
			}
		} else if (strcmp(buf, "MODINFO_M_FS_USAGE") == 0) {
			if ((mod->m_fs_usage =
			    read_contentsrecord_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_CONTENTSRECORD;
				break;
			}
		} else if (strcmp(buf, "END_MODINFO") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_modinfo(mod);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading modinfo: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (mod);
}

/*
 * read_media_from_pipe
 *	Read a Media structure and all of its constituent members from a \
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read Media from
 * Returns:
 *	Media *		- Pointer to Media read from the file stream.
 *			The Media returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Media from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Media *
read_media_from_pipe(FILE *fp)
{
	Media		*media;
	int		err = 0;
	char		buf[BUFSIZ];

	media = (Media *)xcalloc(sizeof (Media));

	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "med_type=") == 0) {
			media->med_type = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "med_status=") == 0) {
			media->med_status = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "med_machine=") == 0) {
			media->med_machine = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "med_device=") == 0) {
			media->med_device = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "med_dir=") == 0) {
			media->med_dir = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "med_volume=") == 0) {
			media->med_volume = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "med_flags=") == 0) {
			media->med_flags = atoi(get_value(buf, '='));
		} else if (strcmp(buf, "MEDIA_MED_CAT") == 0) {
			if ((media->med_cat =
			    read_module_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_MODULE;
				break;
			}
		} else if (strcmp(buf, "MEDIA_MED_HOSTNAME") == 0) {
			if ((media->med_hostname =
			    read_stringlist_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_STRINGLIST;
				break;
			}
		} else if (STRNCMPC(buf, "med_zonename=") == 0) {
			media->med_zonename = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "END_MEDIA") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	/*
	 * Skipping the following members of Media because they are
	 * either not yet set after calling load_installed() to load
	 * installed data, or they belong only to the new Media.
	 */
	media->med_cur_prod = NULL;
	media->med_cur_cat = NULL;
	media->med_deflt_prod = NULL;
	media->med_deflt_cat = NULL;
	media->med_upg_from = NULL;
	media->med_upg_to = NULL;

	if (err != 0) {
		free_media(media);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading media: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (media);
}

/*
 * read_product_from_pipe
 *	Read a Product structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read Product from
 * Returns:
 *	Product *	- Pointer to Product read from the file stream.
 *			The Product returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Product from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Product *
read_product_from_pipe(FILE *fp)
{
	Product		*prod;
	Node		*n;
	Module		*loc, *clst, *cursub;
	int		err = 0;
	char		buf[BUFSIZ];

	prod = (Product *)xcalloc(sizeof (Product));

	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "p_name=") == 0) {
			prod->p_name = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "p_version=") == 0) {
			prod->p_version = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "p_rev=") == 0) {
			prod->p_rev = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "p_status=") == 0) {
			prod->p_status = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "p_id=") == 0) {
			prod->p_id = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "p_pkgdir=") == 0) {
			prod->p_pkgdir = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "p_instdir=") == 0) {
			prod->p_instdir = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "PRODUCT_P_ARCHES") == 0) {
			if ((prod->p_arches = read_arch_from_pipe(fp)) ==
			    NULL) {
				err = SP_PIPE_ERR_READ_ARCH;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_SWCFG") == 0) {
			if ((prod->p_swcfg =
			    read_sw_config_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_SW_CONFIG;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_PLATGRP") == 0) {
			if ((prod->p_platgrp =
			    read_platgroup_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PLATGROUP;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_HWCFG") == 0) {
			if ((prod->p_hwcfg =
			    read_hw_config_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_HW_CONFIG;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_SW_4X") == 0) {
			if ((prod->p_sw_4x =
			    read_modinfo_list_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_MODINFO_LIST;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_PACKAGES") == 0) {
			if ((prod->p_packages =
			    read_modinfo_list_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_MODINFO_LIST;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_CLUSTERS") == 0) {
			prod->p_clusters = getlist();

			while (fgets(buf, BUFSIZ, fp) != NULL) {
			buf[strlen(buf) - 1] = '\0';
			if (strcmp(buf, "P_CLUSTERS_NODE") == 0) {
				if ((n = read_module_node_from_pipe(fp,
				    B_FALSE)) == NULL) {
					err =
					    SP_PIPE_ERR_READ_MODULE_NODE;
					goto done;
				}

				clst = (Module *)n->data;

			while (fgets(buf, BUFSIZ, fp) != NULL) {
				buf[strlen(buf) - 1] = '\0';
				if (strcmp(buf, "NODE_SUB") == 0) {
					if (clst->sub == NULL) {
						clst->sub = cursub =
						    (Module *)xcalloc(
						    sizeof (Module));
					cursub->head = cursub;
					cursub->parent = clst;
				} else {
					cursub = clst->sub;
					while (cursub->next)
					    cursub = cursub->next;
					cursub->next = (Module *)xcalloc(
					    sizeof (Module));
					cursub->next->head = cursub->head;
					cursub->next->parent = cursub->parent;
					cursub->next->prev = cursub;
					cursub = cursub->next;
				}
				while (fgets(buf, BUFSIZ, fp) != NULL) {
					buf[strlen(buf) - 1] = '\0';
					if (STRNCMPC(buf, "type=") == 0) {
					    cursub->type =
						atoi(get_value(buf, '='));
					} else if (STRNCMPC(buf,
					    "m_pkgid=") == 0) {
						cursub->info.mod =
						    (Modinfo *)xcalloc(
						    sizeof (Modinfo));
						cursub->info.mod->m_pkgid =
						    xstrdup(get_value(buf,
						    '='));
					} else if (strcmp(buf, "END_NODE_SUB")
					    == 0) {
						break;
					} else {
						err =
						SP_PIPE_ERR_READ_INVALID_LINE;
						goto done;
					}
				}
				} else if (strcmp(buf, "END_P_CLUSTERS_NODE")
				    == 0) {
					addnode(prod->p_clusters, n);
					break;
				} else {
					err = SP_PIPE_ERR_READ_INVALID_LINE;
					goto done;
				}
			}
			} else if (strcmp(buf, "END_PRODUCT_P_CLUSTERS") == 0) {
				break;
			} else {
				err = SP_PIPE_ERR_READ_INVALID_LINE;
				goto done;
			}
			}
		} else if (strcmp(buf, "PRODUCT_P_LOCALE") == 0) {
			if (prod->p_locale == NULL) {
				if ((prod->p_locale = loc =
				    read_module_from_pipe(fp)) == NULL) {
					err = SP_PIPE_ERR_READ_MODULE;
					break;
				}
				loc->head = loc;
			} else {
				loc = prod->p_locale;
				while (loc->next)
					loc = loc->next;
				if ((loc->next = read_module_from_pipe(fp)) ==
				    NULL) {
					err = SP_PIPE_ERR_READ_MODULE;
					break;
				}
				loc->next->prev = loc;
				loc->next->head = loc->head;
				loc = loc->next;
			}

			while (fgets(buf, BUFSIZ, fp) != NULL) {
				buf[strlen(buf) - 1] = '\0';
				if (strcmp(buf, "PRODUCT_P_LOCALE_SUB") == 0) {
				if (loc->sub == NULL) {
					loc->sub = cursub =
					    (Module *)xcalloc(
					    sizeof (Module));
					cursub->head = cursub;
					cursub->parent = loc;
				} else {
					cursub = loc->sub;
					while (cursub->next)
						cursub = cursub->next;
						cursub->next =
						    (Module *)xcalloc(
						    sizeof (Module));
						cursub->next->prev = cursub;
						cursub->next->head =
						    cursub->head;
						cursub->next->parent =
						    cursub->parent;
						cursub = cursub->next;
					}

					while (fgets(buf, BUFSIZ, fp) !=
					    NULL) {
					buf[strlen(buf) - 1] = '\0';
					if (STRNCMPC(buf, "type=") == 0) {
						cursub->type =
						    atoi(get_value(buf, '='));
					} else if (STRNCMPC(buf,
					    "m_pkgid=") == 0) {
						cursub->info.mod =
						    (Modinfo *)xcalloc(
						    sizeof (Modinfo));
						cursub->info.mod->m_pkgid =
						    xstrdup(get_value(buf,
						    '='));
					} else if (strcmp(buf,
					    "END_PRODUCT_P_LOCALE_SUB") == 0) {
						break;
					} else {
						err =
						SP_PIPE_ERR_READ_INVALID_LINE;
						goto done;
					}
					}
				} else if (strcmp(buf, "END_PRODUCT_P_LOCALE")
				    == 0) {
					break;
				} else {
					err = SP_PIPE_ERR_READ_INVALID_LINE;
					goto done;
				}
			}
		} else if (strcmp(buf, "PRODUCT_P_GEO") == 0) {
			if ((prod->p_geo = read_module_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_MODULE;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_CD_INFO") == 0) {
			if ((prod->p_cd_info =
			    read_module_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_MODULE;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_OS_INFO") == 0) {
			if ((prod->p_os_info =
			    read_module_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_MODULE;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_ORPHAN_PATCH") == 0) {
			if ((prod->p_orphan_patch =
			    read_modinfo_node_from_pipe(fp, B_TRUE)) == NULL) {
				err = SP_PIPE_ERR_READ_MODINFO_NODE;
				break;
			}
		} else if (strncmp(buf, "p_rootdir=", 10) == 0) {
			prod->p_rootdir = xstrdup(get_value(buf, '='));

		/*
		 * Skipping the following members of a Product because they
		 * are either not yet set after calling load_installed() to
		 * load installed Product data, or they belong only to
		 * new Product.
		 *
		 * p_cur_meta
		 * p_cur_cluster
		 * p_cur_pkg
		 * p_cur_cat
		 * p_deflt_meta
		 * p_deflt_cluster
		 * p_deflt_pkg
		 * p_deflt_cat
		 * p_view_from
		 * p_view_4x
		 * p_view_pkg
		 * p_view_cluster
		 * p_view_locale
		 * p_view_geo
		 * p_view_arches
		 * p_next_view
		 */

		} else if (strcmp(buf, "PRODUCT_P_CATEGORIES") == 0) {
			if ((prod->p_categories =
			    read_module_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_MODULE;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_PATCHES") == 0) {
			if ((prod->p_patches =
			    read_patch_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PATCH;
				break;
			}
		} else if (strcmp(buf, "PRODUCT_P_MODFILE_LIST") == 0) {
			if ((prod->p_modfile_list =
			    read_stringlist_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_STRINGLIST;
				break;
			}
		} else if (strncmp(buf, "p_zonename=", 11) == 0) {
			prod->p_zonename = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "PRODUCT_P_INHERITEDDIRS") == 0) {
			if ((prod->p_inheritedDirs =
			    read_charpp_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_CHARPP;
				break;
			}
		} else if (strcmp(buf, "END_PRODUCT") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	/* Set the p_current_view value to itself */
	prod->p_current_view = prod;

done:
	if (err != 0) {
		free_prod(prod);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading product: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}
	return (prod);

}

/*
 * read_locale_from_pipe
 *	Read a Locale and all of its constituent members from a file stream.
 * Parameters:
 *	fp		- FILE stream to read Locale from
 * Returns:
 *	Product *	- Pointer to Locale read from the file stream.
 *			The Locale returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Locale from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Locale *
read_locale_from_pipe(FILE *fp)
{
	Locale		*locale;
	char		buf[BUFSIZ];
	int		err = 0;

	locale = (Locale *)xcalloc(sizeof (Locale));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "l_locale=") == 0) {
			locale->l_locale = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "l_language=") == 0) {
			locale->l_language = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "l_selected=") == 0) {
			locale->l_selected = atoi(get_value(buf, '='));
		} else if (strcmp(buf, "END_LOCALE") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		if (locale->l_locale)
			free(locale->l_locale);
		if (locale->l_language)
			free(locale->l_language);
		free(locale);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading locale: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (locale);
}

/*
 * read_geo_from_pipe
 *	Read a Geo and all of its constituent members from a file stream.
 * Parameters:
 *	fp		- FILE stream to read Geo from
 * Returns:
 *	Geo *		- Pointer to Geo read from the file stream.
 *			The Geo returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Geo from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Geo *
read_geo_from_pipe(FILE *fp)
{
	Geo		*geo;
	char		buf[BUFSIZ];
	int		err = 0;

	geo = (Geo *)xcalloc(sizeof (Geo));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "g_geo=") == 0) {
			geo->g_geo = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "g_name=") == 0) {
			geo->g_name = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "g_selected=") == 0) {
			geo->g_selected = atoi(get_value(buf, '='));
		} else if (strcmp(buf, "GEO_G_LOCALES") == 0) {
			if ((geo->g_locales =
			    read_stringlist_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_STRINGLIST;
				break;
			}
		} else if (strcmp(buf, "END_GEO") == 0)
			break;
		else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		if (geo->g_geo)
			free(geo->g_geo);
		if (geo->g_name)
			free(geo->g_name);
		if (geo->g_locales)
			StringListFree(geo->g_locales);
		free(geo);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading geo: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (geo);
}

/*
 * read_caegory_from_pipe
 *	Read a Category structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read Category from
 * Returns:
 *	Category *	- Pointer to Category read from the file stream.
 *			The Category returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Category from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Category *
read_category_from_pipe(FILE *fp)
{
	Category	*cat;
	char		buf[BUFSIZ];
	int		err = 0;

	cat = (Category *)xcalloc(sizeof (Category));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "cat_name=") == 0) {
			cat->cat_name = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "END_CATEGORY") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err) {
		if (cat->cat_name)
			free(cat->cat_name);
		free(cat);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading category: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (cat);
}

/*
 * read_l10n_from_pipe
 *	Read a L10N structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read L10N from
 * Returns:
 *	L10N *		- Pointer to L10N read from the file stream.
 *			The L10N returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading L10N from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
L10N *
read_l10n_from_pipe(FILE *fp)
{
	L10N	*l10n;
	int	err = 0;
	char	buf[BUFSIZ];

	l10n = (L10N *)xcalloc(sizeof (L10N));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "l10n_package=") == 0) {
			/*
			 * Create a blank Modinfo with just the m_pkgid
			 * filled in.  The caller who's reading this
			 * modinfo needs to find it in the Product's
			 * p_package list to set the pointer accordingly.
			 */
			l10n->l10n_package =
			    (Modinfo *)xcalloc(sizeof (Modinfo));
			l10n->l10n_package->m_pkgid =
			    xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "L10N_L10N_NEXT") == 0) {
			if ((l10n->l10n_next =
			    read_l10n_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_L10N;
				break;
			}
		} else if (strcmp(buf, "END_L10N") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		if (l10n->l10n_package) {
			if (l10n->l10n_package->m_pkgid) {
				free(l10n->l10n_package->m_pkgid);
			}
			free(l10n->l10n_package);
		}
		free(l10n);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading l10n: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (l10n);
}

/*
 * read_pkgslocalized_from_pipe
 *	Read a PkgsLocalized structure and all of its constituent members
 *	from a file stream.
 * Parameters:
 *	fp		- FILE stream to read PkgsLocalized from
 * Returns:
 *	PkgsLocalized *	- Pointer to PkgsLocalized read from the file stream.
 *			The PkgsLocalized returned is in newly allocated
 *			storage.  It is up to the caller to free it when it is
 *			no longer needed.
 *	NULL		- Error while reading PkgsLocalized from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
PkgsLocalized *
read_pkgslocalized_from_pipe(FILE *fp)
{
	PkgsLocalized	*p;
	int		err = 0;
	char		buf[BUFSIZ];

	p = (PkgsLocalized *)xcalloc(sizeof (PkgsLocalized));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "pkg_lclzd=") == 0) {
			/*
			 * Create a blank Modinfo with just the m_pkgid
			 * filled in.  The caller who's reading this
			 * modinfo needs to find it in the Product's
			 * p_package list to set the pointer accordingly.
			 */
			p->pkg_lclzd = (Modinfo *)xcalloc(sizeof (Modinfo));
			p->pkg_lclzd->m_pkgid = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "PKGSLOCALIZED_NEXT") == 0) {
			if ((p->next =
			    read_pkgslocalized_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PKGSLOCALIZED;
				break;
			}
		} else if (strcmp(buf, "END_PKGSLOCALIZED") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_pkgs_lclzd(p);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading pkgslocalized: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (p);
}

/*
 * read_modinfo_node_from_pipe
 *	Read a Node structure and all of its constituent members from a
 *	file stream.  The Node structure being read in has a Modinfo
 *	structure as its data value.
 * Parameters:
 *	fp		- FILE stream to read Node from
 *	follow_link	- flag to specify whether or not to attempt to
 *			read the next node from the pipe.
 * Returns:
 *	Node *		- Pointer to Node read from the file stream.
 *			The Node returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Node from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Node *
read_modinfo_node_from_pipe(FILE *fp, boolean_t follow_link)
{
	Node	*n;
	int	err = 0;
	char	buf[BUFSIZ];

	n = getnode();
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "key=") == 0) {
			n->key = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "MODINFO_NODE_DATA") == 0) {
			if ((n->data =
			    (void *) read_modinfo_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_MODINFO;
				break;
			}
		} else if (strcmp(buf, "MODINFO_NODE_NEXT") == 0) {
			if (!follow_link) {
				err = SP_PIPE_ERR_READ_INVALID_LINE;
				break;
			}
			if ((n->next = read_modinfo_node_from_pipe(fp,
			    follow_link)) == NULL) {
				err = SP_PIPE_ERR_READ_MODINFO_NODE;
				break;
			}

			n->next->prev = n;

		} else if (strcmp(buf, "END_MODINFO_NODE") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	/* Set the delproc function pointer for this modinfo node */
	n->delproc = &free_np_modinfo;

	if (err != 0) {
		free(n->key);
		free_np_modinfo(n);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading modinfo node: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (n);
}

/*
 * read_module_node_from_pipe
 *	Read a Node structure and all of its constituent members from a
 *	file stream.  The Node structure being read in has a Module
 *	structure as its data value.
 * Parameters:
 *	fp		- FILE stream to read Node from
 *	follow_link	- flag to specify whether or not to attempt to
 *			read the next node from the pipe.
 * Returns:
 *	Node *		- Pointer to Node read from the file stream.
 *			The Node returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Node from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Node *
read_module_node_from_pipe(FILE *fp, boolean_t follow_link)
{
	Node	*n;
	int	err = 0;
	char	buf[BUFSIZ];

	n = getnode();
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "key=") == 0) {
			n->key = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "MODULE_NODE_DATA") == 0) {
			if ((n->data =
			    (void *) read_module_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_MODULE;
				break;
			}
		} else if (strcmp(buf, "MODULE_NODE_NEXT") == 0) {
			if (!follow_link) {
				err = SP_PIPE_ERR_READ_INVALID_LINE;
				break;
			}

			if ((n->next = read_module_node_from_pipe(fp,
			    follow_link)) == NULL) {
				err = SP_PIPE_ERR_READ_MODULE_NODE;
				break;
			}

			n->next->prev = n;

		} else if (strcmp(buf, "END_MODULE_NODE") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	/* Set the delproc function pointer for this module node */
	n->delproc = &free_np_module;

	if (err != 0) {
		free(n->key);
		free_np_module(n);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading module node: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (n);
}

/*
 * read_depend_from_pipe
 *	Read a Depend structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read Depend from
 * Returns:
 *	Depend *	- Pointer to Depend read from the file stream.
 *			The Depend returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Depend from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Depend *
read_depend_from_pipe(FILE *fp)
{
	Depend	*depend;
	int	err = 0;
	char	buf[BUFSIZ];

	depend = (Depend *)xcalloc(sizeof (Depend));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "d_pkgid=") == 0) {
			depend->d_pkgid = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "d_pkgidb=") == 0) {
			depend->d_pkgidb = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "d_version=") == 0) {
			depend->d_version = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "d_arch=") == 0) {
			depend->d_arch = xstrdup(get_value(buf, '-'));
		} else if (STRNCMPC(buf, "d_zname=") == 0) {
			depend->d_zname = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "d_type=") == 0) {
			depend->d_type = atoi(get_value(buf, '='));
		} else if (strcmp(buf, "DEPEND_D_NEXT") == 0) {
			if ((depend->d_next =
			    read_depend_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_DEPEND;
				break;
			}
			depend->d_next->d_prev = depend;
		} else if (strcmp(buf, "END_DEPEND") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_depends(depend);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading depend: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (depend);
}

/*
 * read_filepp_from_pipe
 *	Read an array of File structures and all of its constituent members
 *	from a file stream.
 * Parameters:
 *	fp		- File stream to read array of File structures from
 * Returns:
 *	File **		- Pointer to File array read from the file stream.
 *			The File ** returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading File ** from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
File **
read_filepp_from_pipe(FILE *fp)
{
	File		**f = NULL;
	char		buf[BUFSIZ];
	int		n_files = 0;
	int		err = 0;

	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (strcmp(buf, "FILEPP_FILE") == 0) {
			f = (File **)xrealloc(f,
			    (n_files + 2) * sizeof (File *));

			if ((f[n_files] = read_file_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_FILE;
				break;
			}
			f[n_files + 1] = NULL;
			n_files++;
		} else if (strcmp(buf, "END_FILEPP") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		if (f) {
			while (n_files && f[--n_files]) {
				free_file(f[n_files]);
			}
			free(f);
		}
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading filepp: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (f);
}

/*
 * read_file_from_pipe
 *	Read a File structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read File from
 * Returns:
 *	File *		- Pointer to File read from the file stream.
 *			The File returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading File from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
File *
read_file_from_pipe(FILE *fp)
{
	File		*f;
	int		err = 0;
	char		buf[BUFSIZ];

	f = (File *)xcalloc(sizeof (File));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "f_path=") == 0) {
			f->f_path = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "f_name=") == 0) {
			f->f_name = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "f_type=") == 0) {
			f->f_type = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "f_args=") == 0) {
			f->f_args = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "END_FILE") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	/* Skipping f_data, set it to NULL */
	f->f_data = NULL;

	if (err != 0) {
		free_file(f);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading file: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (f);
}

/*
 * read_pkg_hist_from_pipe
 *	Read a pkg_hist structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read pkg_hist from
 * Returns:
 *	pkg_hist *	- Pointer to pkg_hist read from the file stream.
 *			The pkg_hist returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading pkg_hist from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
struct pkg_hist *
read_pkg_hist_from_pipe(FILE *fp)
{
	struct pkg_hist	*ph;
	int		err = 0;
	char		buf[BUFSIZ];

	ph = (struct pkg_hist *)xcalloc(sizeof (struct pkg_hist));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "prod_rm_list=") == 0) {
			ph->prod_rm_list = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "replaced_by=") == 0) {
			ph->replaced_by = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "deleted_files=") == 0) {
			ph->deleted_files = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "cluster_rm_list=") == 0) {
			ph->cluster_rm_list = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "ignore_list=") == 0) {
			ph->ignore_list = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "to_be_removed=") == 0) {
			ph->to_be_removed = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "needs_pkgrm=") == 0) {
			ph->needs_pkgrm = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "basedir_change=") == 0) {
			ph->basedir_change = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "ref_count=") == 0) {
			ph->ref_count = atoi(get_value(buf, '='));
		} else if (strcmp(buf, "PKG_HIST_HIST_NEXT") == 0) {
			if ((ph->hist_next =
			    read_pkg_hist_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PKG_HIST;
				break;
			}
		} else if (strcmp(buf, "END_PKG_HIST") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		if (ph->prod_rm_list)
			free(ph->prod_rm_list);
		if (ph->replaced_by)
			free(ph->replaced_by);
		if (ph->deleted_files)
			free(ph->deleted_files);
		if (ph->cluster_rm_list)
			free(ph->cluster_rm_list);
		if (ph->ignore_list)
			free(ph->ignore_list);
		free(ph);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading pkg_hist: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}
	return (ph);
}

/*
 * read_filediff_from_pipe
 *	Read a filediff structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read filediff from
 *	follow_link	- flag to specify whether or not to attempt to
 *			read the next filediff from the pipe.
 * Returns:
 *	filediff *	- Pointer to filediff read from the file stream.
 *			The filediff returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading filediff from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
struct filediff *
read_filediff_from_pipe(FILE *fp, boolean_t follow_link)
{
	struct filediff	*diff, *diff_cur, *diff_save;
	char		pkgid[MAXPKGNAME_LENGTH];
	Module		*newmediamod;
	Node		*n;
	Modinfo		*mi;
	int		err = 0;
	char		buf[BUFSIZ];

	diff = (struct filediff *)xcalloc(sizeof (struct filediff));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (strcmp(buf, "FILEDIFF_PKG_INFO_PTR") == 0) {
			if ((diff->pkg_info_ptr =
			    read_pkg_info_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PKG_HIST;
				break;
			}
		/*
		 * owning_pkg
		 *
		 * NOTE: owning_pkg is not piped across because it is just
		 * just a reference pointer to the modinfo of which this
		 * filediff belongs.  When reading a modinfo, it will set
		 * its filediff's owning_pkg to itself.
		 */
		} else if (STRNCMPC(buf, "replacing_pkg=") == 0) {
			/*
			 * replacing_pkg is a reference pointer to a
			 * package's modinfo from the new media's product
			 * p_package list.  We find that pointer here
			 * based on the pkgid and set it to replacing_pkg
			 */
			(void) strlcpy(pkgid, get_value(buf, '='),
			    MAXPKGNAME_LENGTH);
			newmediamod = get_newmedia();
			if ((n =
			    findnode(newmediamod->sub->info.prod->p_packages,
			    pkgid)) == NULL) {
				err = SP_PIPE_ERR_READ_FINDNODE;
				break;
			}
			if ((mi = (Modinfo *)n->data) != NULL) {
				diff->replacing_pkg = mi;
			} else {
				err = SP_PIPE_ERR_READ_FINDNODE;
				break;
			}
		} else if (STRNCMPC(buf, "diff_flags=") == 0) {
			diff->diff_flags = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "linkptr=") == 0) {
			diff->linkptr = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "link_found=") == 0) {
			diff->link_found = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "majmin=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(diff->majmin)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "act_mode=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(diff->act_mode)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "act_uid=") == 0) {
			diff->act_uid = (uid_t)atol(get_value(buf, '='));
		} else if (STRNCMPC(buf, "act_gid=") == 0) {
			diff->act_gid = (gid_t)atol(get_value(buf, '='));
		} else if (STRNCMPC(buf, "exp_type=") == 0) {
			diff->exp_type = *(get_value(buf, '='));
		} else if (STRNCMPC(buf, "actual_type=") == 0) {
			diff->actual_type = *(get_value(buf, '='));
		} else if (STRNCMPC(buf, "pkgclass=") == 0) {
			(void) strlcpy(diff->pkgclass, get_value(buf, '='),
			    sizeof (diff->pkgclass));
		} else if (STRNCMPC(buf, "component_path=") == 0) {
			/*
			 * this use of component_path overflows FSspace
			 * so that extra space must be allocated for the path
			 */
			char cpbuf[MAXPATHLEN];
			(void) strlcpy(cpbuf, get_value(buf, '='),
			    sizeof (cpbuf));
			diff = xrealloc(diff, sizeof (struct filediff) +
			    strlen(cpbuf));
			(void) strcpy(diff->component_path, cpbuf);
		} else if (strcmp(buf, "FILEDIFF_DIFF_NEXT") == 0) {
			if (follow_link) {
				if ((diff->diff_next =
				    read_filediff_from_pipe(fp, follow_link)) ==
				    NULL) {
					err = SP_PIPE_ERR_READ_FILEDIFF;
					break;
				}
			}
		} else if (strcmp(buf, "END_FILEDIFF") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		for (diff_cur = diff; diff_cur; diff_cur = diff_save) {
			diff_save = diff_cur->diff_next;
			free_pkg_info(diff_cur->pkg_info_ptr);
			free(diff_cur->linkptr);
			free(diff_cur->link_found);
			free(diff_cur);
		}

		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading filediff: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}
	return (diff);
}

/*
 * read_patch_num_from_pipe
 *	Read a patch_num structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read patch_num from
 * Returns:
 *	patch_num *	- Pointer to patch_num read from the file stream.
 *			The patch_num returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading patch_num from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
struct patch_num *
read_patch_num_from_pipe(FILE *fp)
{
	struct patch_num	*pn;
	int			err = 0;
	char			buf[BUFSIZ];

	pn = (struct patch_num *)xcalloc(sizeof (struct patch_num));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "patch_num_id=") == 0) {
			pn->patch_num_id = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "patch_num_rev_string=") == 0) {
			pn->patch_num_rev_string = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "patch_num_rev=") == 0) {
			if (sscanf(get_value(buf, '='), "%u",
			    &pn->patch_num_rev) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (strcmp(buf, "PATCH_NUM_NEXT") == 0) {
			if ((pn->next = read_patch_num_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PATCH_NUM;
				break;
			}
		} else if (strcmp(buf, "END_PATCH_NUM") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_patch_num(pn);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading patch_num: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (pn);
}

/*
 * read_stringlist_from_pipe
 *	Read a StringList structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read StringList from
 * Returns:
 *	StringList *	- Pointer to StringList read from the file stream.
 *			The StringList returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading StringList from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
StringList *
read_stringlist_from_pipe(FILE *fp)
{
	StringList	*sl = NULL;
	int		err = 0;
	char		buf[BUFSIZ];

	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "string_ptr=") == 0) {
			if (StringListAdd(&sl, get_value(buf, '=')) != 0) {
				err = SP_PIPE_ERR_READ_STRINGLISTADD;
				break;
			}
		} else if (strcmp(buf, "END_STRINGLIST") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		StringListFree(sl);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading stringlist: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (sl);
}

FILE	*open_debug_print_file();

/*
 * read_contentsrecord_from_pipe
 *	Read a ContentsRecord structure and all of its constituent members
 *	from a file stream.
 * Parameters:
 *	fp		- FILE stream to read ContentsRecord from
 * Returns:
 *	ContentsRecord *	- Pointer to ContentsRecord read from the
 *			file stream.  The ContentsRecord returned is in
 *			newly allocated storage.  It is up to the caller to
 *			free it when it is no longer needed.
 *	NULL		- Error while reading ContentsRecord from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
ContentsRecord *
read_contentsrecord_from_pipe(FILE *fp)
{
	ContentsRecord	*cr, *cr_cur, *cr_save;
	int		err = 0;
	char		buf[BUFSIZ];

	cr = (ContentsRecord *)xcalloc(sizeof (ContentsRecord));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "ctsrec_idx=") == 0) {
			cr->ctsrec_idx = atoi(get_value(buf, '='));
		} else if (strcmp(buf, "CONTENTSRECORD_CTSREC_BRKDN") == 0) {
			if (read_contentsbrkdn_from_pipe(fp,
			    &(cr->ctsrec_brkdn)) != 0) {
				err = SP_PIPE_ERR_READ_CONTENTSBRKDN;
				break;
			}
		} else if (strcmp(buf, "CONTENTSRECORD_NEXT") == 0) {
			if ((cr->next =
			    read_contentsrecord_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_CONTENTSRECORD;
				break;
			}
		} else if (strcmp(buf, "END_CONTENTSRECORD") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		for (cr_cur = cr; cr_cur; cr_cur = cr_save) {
			cr_save = cr_cur->next;
			free(cr_cur);
		}
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading contentsrecord: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (cr);
}

/*
 * read_contentsbrkdn_from_pipe
 *	Read a  structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read L10N from
 *	*cb		- pointer to ContentsBrkdn structure to modify
 * Returns:
 *	0		- ContentsBrkdn struture was read in correctly
 *			and the cb passed in was updated.
 *	-1		-  Error while reading ContentsBrkdn from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
int
read_contentsbrkdn_from_pipe(FILE *fp, ContentsBrkdn *cb)
{
	int		err = 0;
	char		buf[BUFSIZ];

	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "contents_packaged=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(cb->contents_packaged)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "contents_nonpkg=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(cb->contents_nonpkg)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "contents_products=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(cb->contents_products)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "contents_devfs=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(cb->contents_devfs)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "contents_savedfiles=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(cb->contents_savedfiles)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "contents_pkg_ovhd=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(cb->contents_pkg_ovhd)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "contents_patch_ovhd=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(cb->contents_patch_ovhd)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "contents_inodes_used=") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(cb->contents_inodes_used)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (strcmp(buf, "END_CONTENTSBRKDN") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading contentsbrkdn: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (-1);
	}

	return (0);
}

/*
 * read_charpp_from_pipe
 *	Read an array of strings from a file stream.
 * Parameters:
 *	fp		- FILE stream to read array of strings from
 * Returns:
 *	char **		- Pointer to an array of strings read from the file
 *			stream.  The char ** returned is in newly allocated
 *			storage.  It is up to the caller to free it when it is
 *			no longer needed.
 *	NULL		- Error while reading char ** from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
char **
read_charpp_from_pipe(FILE *fp)
{
	char	**sa = NULL;
	int	n_strs = 0;
	int	err = 0;
	char	buf[BUFSIZ];

	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "string=") == 0) {
			sa = (char **)xrealloc(sa,
			    (n_strs + 2) * sizeof (char *));
			sa[n_strs] = xstrdup(get_value(buf, '='));
			sa[n_strs + 1] = NULL;
			n_strs++;
		} else if (strcmp(buf, "END_CHARPP") == 0)
			break;
		else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err) {
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading charpp: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (sa);
}

/*
 * read_arch_from_pipe
 *	Read a Arch structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read Arch from
 * Returns:
 *	Arch *		- Pointer to Arch read from the file stream.
 *			The Arch returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Arch from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Arch *
read_arch_from_pipe(FILE *fp)
{
	Arch	*arch;
	int	err = 0;
	char	buf[BUFSIZ];

	arch = (Arch *)xcalloc(sizeof (Arch));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "a_arch=") == 0) {
			arch->a_arch = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "a_selected=") == 0) {
			arch->a_selected = atoi(get_value(buf, '='));
		} else if (STRNCMPC(buf, "a_loaded=") == 0) {
			arch->a_loaded = atoi(get_value(buf, '='));
		} else if (strcmp(buf, "ARCH_A_PLATFORMS") == 0) {
			if ((arch->a_platforms =
			    read_stringlist_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_STRINGLIST;
				break;
			}
		} else if (strcmp(buf, "ARCH_A_NEXT") == 0) {
			if ((arch->a_next = read_arch_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_ARCH;
				break;
			}
		} else if (strcmp(buf, "END_ARCH") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_arch(arch);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading arch: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (arch);
}

/*
 * read_modinfo_list_from_pipe
 *	Read a List from a file stream.  The List contains Nodes whose data
 *	types are Modinfo structures.
 * Parameters:
 *	fp		- FILE stream to read List from
 * Returns:
 *	List *		- Pointer to List read from the file stream.
 *			The List returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading List from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
List *
read_modinfo_list_from_pipe(FILE *fp)
{
	List	*list;
	Node	*n;
	int	err = 0;
	char	buf[BUFSIZ];

	list = getlist();
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (strcmp(buf, "LIST_MODINFO_NODE") == 0) {
			if ((n =
			    read_modinfo_node_from_pipe(fp, B_FALSE)) == NULL) {
				err = SP_PIPE_ERR_READ_MODINFO_NODE;
				break;
			}
			if (addnode(list, n) != 0) {
				err = SP_PIPE_ERR_READ_ADDNODE;
				break;
			}
		} else if (strcmp(buf, "END_MODINFO_LIST") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_list(list);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading modinfo list: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}
	return (list);
}

/*
 * read_module_list_from_pipe
 *	Read a List from a file stream.  The List contains Nodes whose data
 *	types are Module structures.
 * Parameters:
 *	fp		- FILE stream to read List from
 * Returns:
 *	List *		- Pointer to List read from the file stream.
 *			The List returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading List from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
List *
read_module_list_from_pipe(FILE *fp)
{
	List	*list;
	Node	*n;
	int	err = 0;
	char	buf[BUFSIZ];

	list = getlist();
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (strcmp(buf, "LIST_MODULE_NODE") == 0) {
			if ((n =
			    read_module_node_from_pipe(fp, B_FALSE)) == NULL) {
				err = SP_PIPE_ERR_READ_MODULE_NODE;
				break;
			}
			if (addnode(list, n) != 0) {
				err = SP_PIPE_ERR_READ_ADDNODE;
				break;
			}
		} else if (strcmp(buf, "END_MODULE_LIST") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_list(list);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading module list: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}
	return (list);
}

/*
 * read_pkg_info_from_pipe
 *	Read a pkg_info structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read pkg_info from
 * Returns:
 *	pkg_info *	- Pointer to pkg_info read from the file stream.
 *			The pkg_info returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading pkg_info from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
struct pkg_info *
read_pkg_info_from_pipe(FILE *fp)
{
	struct pkg_info	*pi;
	int		err = 0;
	char		buf[BUFSIZ];

	pi = (struct pkg_info *)xcalloc(sizeof (struct pkg_info));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "name=") == 0) {
			pi->name = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "arch=") == 0) {
			pi->name = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "PKG_INFO_NEXT") == 0) {
			if ((pi->next = read_pkg_info_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PKG_INFO;
				break;
			}
		} else if (strcmp(buf, "END_PKG_INFO") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_pkg_info(pi);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading pkg_info: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (pi);
}

/*
 * read_sw_config_from_pipe
 *	Read a SW_conifg structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read SW_config from
 * Returns:
 *	SW_config *	- Pointer to SW_config read from the file stream.
 *			The SW_config returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading SW_config from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
SW_config *
read_sw_config_from_pipe(FILE *fp)
{
	SW_config	*sw;
	int		err = 0;
	char		buf[BUFSIZ];

	sw = (SW_config *)xcalloc(sizeof (SW_config));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "sw_cfg_name=") == 0) {
			sw->sw_cfg_name = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "SW_CONFIG_SW_CFG_MEMBERS") == 0) {
			if ((sw->sw_cfg_members =
			    read_stringlist_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_STRINGLIST;
				break;
			}
		} else if (STRNCMPC(buf, "sw_cfg_auto=") == 0) {
			sw->sw_cfg_auto = atoi(get_value(buf, '='));
		} else if (strcmp(buf, "SW_CONFIG_NEXT") == 0) {
			if ((sw->next = read_sw_config_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_SW_CONFIG;
				break;
			}
		} else if (strcmp(buf, "END_SW_CONFIG") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_sw_config_list(sw);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading sw_config: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (sw);
}

/*
 * read_hw_config_from_pipe
 *	Read a HW_config structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read HW_config from
 * Returns:
 *	HW_config *	- Pointer to HW_config read from the file stream.
 *			The HW_config returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading HW_config from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
HW_config *
read_hw_config_from_pipe(FILE *fp)
{
	HW_config	*hw;
	int		err = 0;
	char		buf[BUFSIZ];

	hw = (HW_config *)xcalloc(sizeof (HW_config));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "hw_node=") == 0) {
			hw->hw_node = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "hw_testprog=") == 0) {
			hw->hw_testprog = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "hw_testarg=") == 0) {
			hw->hw_testarg = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "HW_CONFIG_HW_SUPPORT_PKGS") == 0) {
			if ((hw->hw_support_pkgs =
			    read_stringlist_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_STRINGLIST;
				break;
			}
		} else if (strcmp(buf, "HW_CONFIG_NEXT") == 0) {
			if ((hw->next = read_hw_config_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_HW_CONFIG;
				break;
			}
		} else if (strcmp(buf, "END_HW_CONFIG") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_hw_config(hw);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading hw_config: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (hw);
}

/*
 * read_platgroup_from_pipe
 *	Read a PlatGroup structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read PlatGroup from
 * Returns:
 *	PlatGroup *	- Pointer to PlatGroup read from the file stream.
 *			The PlatGroup returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading PlatGroup from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
PlatGroup *
read_platgroup_from_pipe(FILE *fp)
{
	PlatGroup	*pg;
	int		err = 0;
	char		buf[BUFSIZ];

	pg = (PlatGroup *)xcalloc(sizeof (PlatGroup));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "pltgrp_name=") == 0) {
			pg->pltgrp_name = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "PLATGROUP_PLTGRP_MEMBERS") == 0) {
			if ((pg->pltgrp_members =
			    read_platform_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PLATFORM;
				break;
			}
		} else if (strcmp(buf, "PLATGROUP_PLTGRP_CONFIG") == 0) {
			if ((pg->pltgrp_config =
			    read_sw_config_from_pipe(fp)) == NULL) {
			    err = SP_PIPE_ERR_READ_SW_CONFIG;
			    break;
			}
		} else if (strcmp(buf, "PLATGROUP_PLTGRP_ALL_CONFIG") ==
		    0) {
			if ((pg->pltgrp_all_config =
			    read_sw_config_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_SW_CONFIG;
				break;
			}
		} else if (STRNCMPC(buf, "pltgrp_isa=") == 0) {
			pg->pltgrp_isa = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "pltgrp_export=") == 0) {
			pg->pltgrp_export = atoi(get_value(buf, '='));
		} else if (strcmp(buf, "PLATGROUP_NEXT") == 0) {
			if ((pg->next = read_platgroup_from_pipe(fp)) ==
			    NULL) {
				err = SP_PIPE_ERR_READ_PLATGROUP;
				break;
			}
		} else if (strcmp(buf, "END_PLATGROUP") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_platgroup(pg);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading platgroup: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (pg);
}

/*
 * read_platform_from_pipe
 *	Read a Platform structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read Platform from
 * Returns:
 *	Platform *	- Pointer to Platform read from the file stream.
 *			The Platform returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading Platform from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
Platform *
read_platform_from_pipe(FILE *fp)
{
	Platform	*pf;
	int		err = 0;
	char		buf[BUFSIZ];

	pf = (Platform *)xcalloc(sizeof (Platform));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "plat_name=") == 0) {
			pf->plat_name = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "plat_uname_id=") == 0) {
			pf->plat_uname_id = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "plat_machine=") == 0) {
			pf->plat_machine = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "plat_group=") == 0) {
			pf->plat_group = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "PLATFORM_PLAT_CONFIG") == 0) {
			if ((pf->plat_config =
			    read_sw_config_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_SW_CONFIG;
				break;
			}
		} else if (strcmp(buf, "PLATFORM_PLAT_ALL_CONFIG") == 0) {
			if ((pf->plat_all_config =
			    read_sw_config_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_SW_CONFIG;
				break;
			}
		} else if (STRNCMPC(buf, "plat_isa=") == 0) {
			pf->plat_isa = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "PLATFORM_NEXT") == 0) {
			if ((pf->next = read_platform_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PLATFORM;
				break;
			}
		} else if (strcmp(buf, "END_PLATFORM") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_platform(pf);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading platform: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (pf);
}

/*
 * read_patch_from_pipe
 *	Read a patch structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read patch from
 * Returns:
 *	patch *		- Pointer to patch read from the file stream.
 *			The patch returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading patch from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
struct patch *
read_patch_from_pipe(FILE *fp)
{
	struct patch	*p;
	int		err = 0;
	char		buf[BUFSIZ];

	p = (struct patch *)xcalloc(sizeof (struct patch));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "patchid=") == 0) {
			p->patchid = xstrdup(get_value(buf, '='));
		} else if (STRNCMPC(buf, "removed=") == 0) {
			p->removed = atoi(get_value(buf, '='));
		} else if (strcmp(buf, "PATCH_PATCHPKGS") == 0) {
			if ((p->patchpkgs =
			    read_patchpkg_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PATCHPKG;
				break;
			}
		} else if (strcmp(buf, "PATCH_NEXT") == 0) {
			if ((p->next = read_patch_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PATCH;
				break;
			}
		} else if (strcmp(buf, "END_PATCH") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		free_patch(p);
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading patch: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (p);
}

/*
 * read_patchpkg_from_pipe
 *	Read a patchpkg structure and all of its constituent members from a
 *	file stream.
 * Parameters:
 *	fp		- FILE stream to read patchpkg from
 * Returns:
 *	patchpkg *	- Pointer to patchpkg read from the file stream.
 *			The patchpkg returned is in newly allocated storage.
 *			It is up to the caller to free it when it is no
 *			longer needed.
 *	NULL		- Error while reading patchpkg from file stream.
 * Status:
 *	semi-private (for internal library use only)
 */
struct patchpkg *
read_patchpkg_from_pipe(FILE *fp)
{
	struct patchpkg	*pp, *ppkg, *next_ppkg;
	int		err = 0;
	char		buf[BUFSIZ];

	pp = (struct patchpkg *)xcalloc(sizeof (struct patchpkg));
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "patchpkg_mod=") == 0) {
			/*
			 * Create a blank Modinfo with just the m_pkgid
			 * filled in.  The caller who's reading this
			 * modinfo needs to find it in the corresponding
			 * package's m_next_patch list to set the pointer
			 * accordingly.
			 */
			pp->pkgmod = (Modinfo *)xcalloc(sizeof (Modinfo));
			pp->pkgmod->m_pkgid = xstrdup(get_value(buf, '='));
		} else if (strcmp(buf, "PATCHPKG_NEXT") == 0) {
			if ((pp->next = read_patchpkg_from_pipe(fp)) == NULL) {
				err = SP_PIPE_ERR_READ_PATCHPKG;
				break;
			}
		} else if (strcmp(buf, "END_PATCHPKG") == 0) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		for (ppkg = pp; ppkg; ppkg = next_ppkg) {
			next_ppkg = ppkg->next;
			ppkg->next = NULL;
			if (ppkg->pkgmod)
				free(ppkg->pkgmod->m_pkgid);
			free(ppkg->pkgmod);
			ppkg->pkgmod = NULL;
			free(ppkg);
		}

		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading patchpkg: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (NULL);
	}

	return (pp);
}

/*
 * write_module_to_pipe
 *	Write a Module structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	mod		- Module to write to stream.
 *	follow_sub	- flag to specify whether or not to write this
 *			Module's submodules to the stream.
 * Return:
 *	0		- Successfully wrote Module to stream.
 *	-1		- Failed to write Module to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_module_to_pipe(FILE *fp, Module *mod, boolean_t follow_sub)
{
	Module	*m;

	(void) fprintf(fp, "type=%d\n", mod->type);
	switch (mod->type) {
	case PACKAGE:
		if (write_modinfo_to_pipe(fp, mod->info.mod) != 0)
			return (-1);
		break;
	case PRODUCT:
	case NULLPRODUCT:
		if (write_product_to_pipe(fp, mod->info.prod) != 0)
			return (-1);
		break;
	case MEDIA:
		if (write_media_to_pipe(fp, mod->info.media) != 0)
			return (-1);
		break;
	case CLUSTER:
	case METACLUSTER:
	case UNBUNDLED_4X:
		if (write_modinfo_to_pipe(fp, mod->info.mod) != 0)
			return (-1);
		break;
	case CATEGORY:
		if (write_category_to_pipe(fp, mod->info.cat) != 0)
			return (-1);
		break;
	case LOCALE:
		if (write_locale_to_pipe(fp, mod->info.locale) != 0)
			return (-1);
		break;
	case GEO:
		if (write_geo_to_pipe(fp, mod->info.geo) != 0)
			return (-1);
		break;
	default:
		/* Other mod types not implemented */
		(void) fprintf(fp, "END_MODULE\n");
		return (0);
	}

	/* Write out the sub module if it has one. */
	if (follow_sub && (m = mod->sub) != NULL) {
		(void) fprintf(fp, "MODULE_SUB\n");

		/*
		 * If this is an installed Product module
		 * (type == NULLPRODUCT), write out blank sub module's
		 * with just the m_pkgid's filled in.  For an installed
		 * Product module, its sub modules are pointers to
		 * metacluster/clusters that are already in the Product's
		 * p_clusters list.  The reader will have to traverse this
		 * Product module's sub modules and set the pointers from
		 * its p_clusters's list accordingly.
		 */
		if (mod->type == NULLPRODUCT) {
			(void) fprintf(fp, "type=%d\n", m->type);
			(void) fprintf(fp, "m_pkgid=%s\n",
			    m->info.mod->m_pkgid);
			(void) fprintf(fp, "END_MODULE\n");
			for (m = m->next; m; m = m->next) {
				(void) fprintf(fp, "MODULE_SUB_NEXT\n");
				(void) fprintf(fp, "type=%d\n", m->type);
				(void) fprintf(fp, "m_pkgid=%s\n",
				    m->info.mod->m_pkgid);
				(void) fprintf(fp, "END_MODULE\n");
			}
		} else {
			if (write_module_to_pipe(fp, m, B_TRUE) != 0)
				return (-1);

			/* Write out the sub's peers */
			for (m = m->next; m; m = m->next) {
				(void) fprintf(fp, "MODULE_SUB_NEXT\n");
				if (write_module_to_pipe(fp, m, B_TRUE) != 0)
					return (-1);
			}
		}
	}

	(void) fprintf(fp, "END_MODULE\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_modinfo_to_pipe
 *	Write a Modinfo structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	mod		- Modinfo to write to stream.
 * Return:
 *	0		- Successfully wrote Modinfo to stream.
 *	-1		- Failed to write Modinfo to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_modinfo_to_pipe(FILE *fp, Modinfo *mod)
{
	int		i;

	(void) fprintf(fp, "m_order=%d\n", mod->m_order);
	(void) fprintf(fp, "m_status=%d\n", mod->m_status);
	(void) fprintf(fp, "m_shared=%d\n", mod->m_shared);
	(void) fprintf(fp, "m_action=%d\n", mod->m_action);
	(void) fprintf(fp, "m_flags=%d\n", mod->m_flags);
	(void) fprintf(fp, "m_refcnt=%d\n", mod->m_refcnt);
	(void) fprintf(fp, "m_sunw_ptype=%d\n", mod->m_sunw_ptype);
	if (mod->m_pkgid)
		(void) fprintf(fp, "m_pkgid=%s\n", mod->m_pkgid);
	if (mod->m_pkginst)
		(void) fprintf(fp, "m_pkginst=%s\n", mod->m_pkginst);
	if (mod->m_pkg_dir)
		(void) fprintf(fp, "m_pkg_dir=%s\n", mod->m_pkg_dir);
	if (mod->m_name)
		(void) fprintf(fp, "m_name=%s\n", mod->m_name);
	if (mod->m_vendor)
		(void) fprintf(fp, "m_vendor=%s\n", mod->m_vendor);
	if (mod->m_version)
		(void) fprintf(fp, "m_version=%s\n", mod->m_version);
	if (mod->m_prodname)
		(void) fprintf(fp, "m_prodname=%s\n", mod->m_prodname);
	if (mod->m_prodvers)
		(void) fprintf(fp, "m_prodvers=%s\n", mod->m_prodvers);
	if (mod->m_arch)
		(void) fprintf(fp, "m_arch=%s\n", mod->m_arch);
	if (mod->m_expand_arch)
		(void) fprintf(fp, "m_expand_arch=%s\n", mod->m_expand_arch);
	if (mod->m_desc)
		(void) fprintf(fp, "m_desc=%s\n", mod->m_desc);
	if (mod->m_category)
		(void) fprintf(fp, "m_category=%s\n", mod->m_category);
	if (mod->m_instdate)
		(void) fprintf(fp, "m_instdate=%s\n", mod->m_instdate);
	if (mod->m_patchid)
		(void) fprintf(fp, "m_patchid=%s\n", mod->m_patchid);
	if (mod->m_locale)
		(void) fprintf(fp, "m_locale=%s\n", mod->m_locale);
	if (mod->m_l10n_pkglist)
		(void) fprintf(fp, "m_l10n_pkglist=%s\n", mod->m_l10n_pkglist);

	/*
	 * m_l10n
	 * m_pkgs_lclzd
	 *
	 * For non-locale packages, m_l10n is a linked list of localization
	 * packages which localized this package.  The L10N structure
	 * contains reference pointers to the localization packages which
	 * are already in the product's p_package list.
	 *
	 * For locale packages, m_pkgs_lclzd is a linked list of packages
	 * which this locale package localizes.  The PkgsLocalized structure
	 * contains reference pointers to packages which are already in the
	 * product's p_package list.
	 *
	 * Because we can not simply pass these reference pointers across
	 * the pipe, we won't.  The reader simply needs to call
	 * localize_packages() on the Product to create the proper
	 * m_l10n and m_pkgs_lclzd lists for every package in its p_package
	 * list.
	 */
	if (mod->m_l10n) {
		(void) fprintf(fp, "MODINFO_M_L10N\n");
		if (write_l10n_to_pipe(fp, mod->m_l10n) != 0)
			return (-1);
	}
	if (mod->m_pkgs_lclzd) {
		(void) fprintf(fp, "MODINFO_M_PKGS_LCLZD\n");
		if (write_pkgslocalized_to_pipe(fp, mod->m_pkgs_lclzd) != 0)
			return (-1);
	}

	/*
	 * m_instance
	 *
	 * For a package, m_instance is a linked list of package modinfos
	 * that are additional instances of this package.  The list of
	 * packages are modinfos that do not already live in the product's
	 * p_package list.  Hence we can safely traverse the list and send
	 * them across the pipe.
	 */
	if (mod->m_instances) {
		(void) fprintf(fp, "MODINFO_M_INSTANCES\n");
		if (write_modinfo_node_to_pipe(fp, mod->m_instances,
		    B_TRUE) != 0)
			return (-1);
	}

	/*
	 * m_next_patch
	 *
	 * For a package, m_next_patch is a linked list of patch modinfos
	 * that patch this package.  The list of patches are modinfos that
	 * do not already live in the products's p_package list.  Hence we
	 * can safely traverse the list and send them across the pipe.
	 */
	if (mod->m_next_patch) {
		(void) fprintf(fp, "MODINFO_M_NEXT_PATCH\n");
		if (write_modinfo_node_to_pipe(fp, mod->m_next_patch,
		    B_TRUE) != 0)
			return (-1);
	}

	/*
	 * m_patchof
	 *
	 * For a patch, m_patchof is a reference pointer to the modinfo of
	 * the package that this patch patches.  The package modinfo is a
	 * Node that already lives in the product's p_package list.  Hence
	 * we do not send it across the pipe.  We send the package's m_pkgid
	 * so that the reader can find the package modinfo and set m_patchof
	 * accordingly.
	 */
	if (mod->m_patchof) {
		(void) fprintf(fp, "m_patchof=%s\n", mod->m_patchof->m_pkgid);
	}

	if (mod->m_pdepends) {
		(void) fprintf(fp, "MODINFO_M_PDEPENDS\n");
		if (write_depend_to_pipe(fp, mod->m_pdepends) != 0)
			return (-1);
	}
	if (mod->m_rdepends) {
		(void) fprintf(fp, "MODINFO_M_RDEPENDS\n");
		if (write_depend_to_pipe(fp, mod->m_rdepends) != 0)
			return (-1);
	}
	if (mod->m_idepends) {
		(void) fprintf(fp, "MODINFO_M_IDEPENDS\n");
		if (write_depend_to_pipe(fp, mod->m_idepends) != 0)
			return (-1);
	}
	if (mod->m_text) {
		(void) fprintf(fp, "MODINFO_M_TEXT\n");
		if (write_filepp_to_pipe(fp, mod->m_text) != 0)
			return (-1);
	}
	if (mod->m_demo) {
		(void) fprintf(fp, "MODINFO_M_DEMO\n");
		if (write_filepp_to_pipe(fp, mod->m_demo) != 0)
			return (-1);
	}
	if (mod->m_install) {
		(void) fprintf(fp, "MODINFO_M_INSTALL\n");
		if (write_file_to_pipe(fp, mod->m_install) != 0)
			return (-1);
	}
	if (mod->m_icon) {
		(void) fprintf(fp, "MODINFO_M_ICON\n");
		if (write_file_to_pipe(fp, mod->m_icon) != 0)
			return (-1);
	}
	if (mod->m_basedir)
		(void) fprintf(fp, "m_basedir=%s\n", mod->m_basedir);
	if (mod->m_instdir)
		(void) fprintf(fp, "m_instdir=%s\n", mod->m_instdir);
	if (mod->m_pkg_hist) {
		(void) fprintf(fp, "MODINFO_M_PKG_HIST\n");
		if (write_pkg_hist_to_pipe(fp, mod->m_pkg_hist) != 0) {
			return (-1);
		}
	}
	(void) fprintf(fp, "m_spooled_size=%ld\n", mod->m_spooled_size);
	(void) fprintf(fp, "m_pkgovhd_size=%lu\n", mod->m_pkgovhd_size);

	(void) fprintf(fp, "MODINFO_M_DEFLT_FS_ARRAY\n");
	for (i = 0; i < N_LOCAL_FS; i++) {
		(void) fprintf(fp, "m_deflt_fs=%ld\n",
		    (ulong) mod->m_deflt_fs[i]);
	}
	(void) fprintf(fp, "END_MODINFO_M_DEFLT_FS_ARRAY\n");

	if (mod->m_filediff) {
		(void) fprintf(fp, "MODINFO_M_FILEDIFF\n");
		if (write_filediff_to_pipe(fp, mod->m_filediff, 1) != 0)
			return (-1);
	}

	if (mod->m_newarch_patches) {
		(void) fprintf(fp, "MODINFO_M_NEWARCH_PATCHES\n");
		if (write_patch_num_to_pipe(fp, mod->m_newarch_patches) != 0)
			return (-1);
	}
	if (mod->m_loc_strlist) {
		(void) fprintf(fp, "MODINFO_M_LOC_STRLIST\n");
		if (write_stringlist_to_pipe(fp, mod->m_loc_strlist) != 0)
			return (-1);
	}

	if (mod->m_fs_usage) {
		(void) fprintf(fp, "MODINFO_M_FS_USAGE\n");
		if (write_contentsrecord_to_pipe(fp, mod->m_fs_usage) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_MODINFO\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_media_to_pipe
 *	Write a Media structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	media		- Media to write to stream.
 * Return:
 *	0		- Successfully wrote Media to stream.
 *	-1		- Failed to write Media to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_media_to_pipe(FILE *fp, Media *media)
{
	(void) fprintf(fp, "med_type=%d\n", media->med_type);
	(void) fprintf(fp, "med_status=%d\n", media->med_status);
	(void) fprintf(fp, "med_machine=%d\n", media->med_machine);
	if (media->med_device)
		(void) fprintf(fp, "med_device=%s\n", media->med_device);
	if (media->med_dir)
		(void) fprintf(fp, "med_dir=%s\n", media->med_dir);
	if (media->med_volume)
		(void) fprintf(fp, "med_volume=%s\n", media->med_volume);
	(void) fprintf(fp, "med_flags=%d\n", media->med_flags);
	if (media->med_cat) {
		(void) fprintf(fp, "MEDIA_MED_CAT\n");
		if (write_module_to_pipe(fp, media->med_cat, B_TRUE) != 0)
			return (-1);
	}
	if (media->med_hostname) {
		(void) fprintf(fp, "MEDIA_MED_HOSTNAME\n");
		if (write_stringlist_to_pipe(fp, media->med_hostname) != 0)
			return (-1);
	}
	if (media->med_zonename)
		(void) fprintf(fp, "med_zonename=%s\n", media->med_zonename);

	/*
	 * Skipping the following members of Media because they are
	 * either not yet set after calling load_installed() to load
	 * installed data, or they belong only to the new Media.
	 *
	 * med_cur_prod
	 * med_cur_cat
	 * med_deflt_prod
	 * med_deflt_cat
	 * med_upg_from
	 * med_upg_to
	 */

	(void) fprintf(fp, "END_MEDIA\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_product_to_pipe
 *	Write a Product structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	product		- Product to write to stream.
 * Return:
 *	0		- Successfully wrote Product to stream.
 *	-1		- Failed to write Product to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_product_to_pipe(FILE *fp, Product *product)
{
	Module	*loc, *clst, *comp, *pkgmod;
	List	*clist;
	Node	*cnode;

	if (product->p_name)
		(void) fprintf(fp, "p_name=%s\n", product->p_name);
	if (product->p_version)
		(void) fprintf(fp, "p_version=%s\n", product->p_version);
	if (product->p_rev)
		(void) fprintf(fp, "p_rev=%s\n", product->p_rev);
	(void) fprintf(fp, "p_status=%d\n", product->p_status);
	if (product->p_id)
		(void) fprintf(fp, "p_id=%s\n", product->p_id);
	if (product->p_pkgdir)
		(void) fprintf(fp, "p_pkgdir=%s\n", product->p_pkgdir);
	if (product->p_instdir)
		(void) fprintf(fp, "p_instdir=%s\n", product->p_instdir);
	if (product->p_arches) {
		(void) fprintf(fp, "PRODUCT_P_ARCHES\n");
		if (write_arch_to_pipe(fp, product->p_arches) != 0)
			return (-1);
	}
	if (product->p_swcfg) {
		(void) fprintf(fp, "PRODUCT_P_SWCFG\n");
		if (write_sw_config_to_pipe(fp, product->p_swcfg) != 0)
			return (-1);
	}
	if (product->p_platgrp) {
		(void) fprintf(fp, "PRODUCT_P_PLATGRP\n");
		if (write_platgroup_to_pipe(fp, product->p_platgrp) != 0)
			return (-1);
	}
	if (product->p_hwcfg) {
		(void) fprintf(fp, "PRODUCT_P_HWCFG\n");
		if (write_hw_config_to_pipe(fp, product->p_hwcfg) != 0)
			return (-1);
	}
	if (product->p_sw_4x) {
		(void) fprintf(fp, "PRODUCT_P_SW_4X\n");
		if (write_modinfo_list_to_pipe(fp, product->p_sw_4x) != 0)
			return (-1);
	}
	if (product->p_packages) {
		(void) fprintf(fp, "PRODUCT_P_PACKAGES\n");
		if (write_modinfo_list_to_pipe(fp, product->p_packages) != 0)
			return (-1);
	}
	if (product->p_clusters) {
		(void) fprintf(fp, "PRODUCT_P_CLUSTERS\n");
		clist = product->p_clusters;
		for (cnode = clist->list->next; cnode && cnode != clist->list;
		    cnode = cnode->next) {

			(void) fprintf(fp, "P_CLUSTERS_NODE\n");
			if (write_module_node_to_pipe(fp, cnode,
			    B_FALSE, B_FALSE) != 0)
					return (-1);

			clst = (Module *)cnode->data;

			for (comp = clst->sub; comp; comp = comp->next) {
				(void) fprintf(fp, "NODE_SUB\n");
				(void) fprintf(fp, "type=%d\n", comp->type);
				(void) fprintf(fp, "m_pkgid=%s\n",
				    comp->info.mod->m_pkgid);
				(void) fprintf(fp,
				    "END_NODE_SUB\n");
			}

			(void) fprintf(fp, "END_P_CLUSTERS_NODE\n");
		}
		(void) fprintf(fp, "END_PRODUCT_P_CLUSTERS\n");
	}

	for (loc = product->p_locale; loc; loc = loc->next) {
		(void) fprintf(fp, "PRODUCT_P_LOCALE\n");
		if (write_module_to_pipe(fp, loc, B_FALSE) != 0)
			return (-1);
		for (pkgmod = loc->sub; pkgmod; pkgmod = pkgmod->next) {
			(void) fprintf(fp, "PRODUCT_P_LOCALE_SUB\n");
			(void) fprintf(fp, "type=%d\n", pkgmod->type);
			(void) fprintf(fp, "m_pkgid=%s\n",
			    pkgmod->info.mod->m_pkgid);
			(void) fprintf(fp, "END_PRODUCT_P_LOCALE_SUB\n");
		}
		(void) fprintf(fp, "END_PRODUCT_P_LOCALE\n");
	}

	if (product->p_geo) {
		(void) fprintf(fp, "PRODUCT_P_GEO\n");
		if (write_module_to_pipe(fp, product->p_geo, B_TRUE) != 0)
			return (-1);
	}
	if (product->p_cd_info) {
		(void) fprintf(fp, "PRODUCT_P_CD_INFO\n");
		if (write_module_to_pipe(fp, product->p_cd_info, B_TRUE) != 0)
		    return (-1);
	}
	if (product->p_os_info) {
		(void) fprintf(fp, "PRODUCT_P_OS_INFO\n");
		if (write_module_to_pipe(fp, product->p_os_info, B_TRUE) != 0)
			return (-1);
	}
	if (product->p_orphan_patch) {
		(void) fprintf(fp, "PRODUCT_P_ORPHAN_PATCH\n");
		if (write_modinfo_node_to_pipe(fp, product->p_orphan_patch,
		    B_TRUE) != 0)
			return (-1);
	}

	if (product->p_rootdir)
		(void) fprintf(fp, "p_rootdir=%s\n", product->p_rootdir);

	/*
	 * Skipping the following members of a Product because they are
	 * either not yet set after calling load_installed() to load
	 * installed Product data, or they belong only to the new Product.
	 *
	 * p_cur_meta
	 * p_cur_cluster
	 * p_cur_pkg
	 * p_cur_cat
	 * p_deflt_meta
	 * p_deflt_cluster
	 * p_deflt_pkg
	 * p_deflt_cat
	 * p_view_from
	 * p_view_4x
	 * p_view_pkg
	 * p_view_cluster
	 * p_view_locale
	 * p_view_geo
	 * p_view_arches
	 * p_next_view
	 */

	if (product->p_categories) {
		(void) fprintf(fp, "PRODUCT_P_CATEGORIES\n");
		if (write_module_to_pipe(fp, product->p_categories, B_TRUE) !=
		    0)
			return (-1);
	}

	/*
	 * p_patches consists of a linked list of patch structures which
	 * contain a linked list of package modinfos which are reference
	 * pointers to modinfos that already exist in a package modinfo's
	 * m_next_patch list.  Hence we don't send across p_patches.
	 * The reader of this Product can walk its p_packages's list running
	 * load_patch() to populate it p_patches list.
	 */
	if (product->p_patches) {
		(void) fprintf(fp, "PRODUCT_P_PATCHES\n");
		if (write_patch_to_pipe(fp, product->p_patches) != 0)
			return (-1);
	}

	if (product->p_modfile_list) {
		(void) fprintf(fp, "PRODUCT_P_MODFILE_LIST\n");
		if (write_stringlist_to_pipe(fp, product->p_modfile_list) != 0)
			return (-1);
	}
	if (product->p_zonename)
		(void) fprintf(fp, "p_zonename=%s\n", product->p_zonename);
	if (product->p_inheritedDirs) {
		(void) fprintf(fp, "PRODUCT_P_INHERITEDDIRS\n");
		if (write_charpp_to_pipe(fp, product->p_inheritedDirs) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_PRODUCT\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_locale_to_pipe
 *	Write a Locale structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	locale		- Locale to write to stream.
 * Return:
 *	0		- Successfully wrote Locale to stream.
 *	-1		- Failed to write Locale to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_locale_to_pipe(FILE *fp, Locale *locale)
{
	if (locale->l_locale)
		(void) fprintf(fp, "l_locale=%s\n", locale->l_locale);
	if (locale->l_language)
		(void) fprintf(fp, "l_language=%s\n", locale->l_language);
	(void) fprintf(fp, "l_selected=%d\n", locale->l_selected);

	(void) fprintf(fp, "END_LOCALE\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_geo_to_pipe
 *	Write a Geo structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	geo		- Geo to write to stream.
 * Return:
 *	0		- Successfully wrote Geo to stream.
 *	-1		- Failed to write Geo to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_geo_to_pipe(FILE *fp, Geo *geo)
{
	if (geo->g_geo)
		(void) fprintf(fp, "g_geo=%s\n", geo->g_geo);
	if (geo->g_name)
		(void) fprintf(fp, "g_name=%s\n", geo->g_name);
	(void) fprintf(fp, "g_selected=%d\n", geo->g_selected);
	if (geo->g_locales) {
		(void) fprintf(fp, "GEO_G_LOCALES\n");
		if (write_stringlist_to_pipe(fp, geo->g_locales) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_GEO\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_category_to_pipe
 *	Write a Gee structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	cat		- Category to write to stream.
 * Return:
 *	0		- Successfully wrote Category to stream.
 *	-1		- Failed to write Category to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_category_to_pipe(FILE *fp, Category *cat)
{
	if (cat->cat_name)
		(void) fprintf(fp, "cat_name=%s\n", cat->cat_name);

	(void) fprintf(fp, "END_CATEGORY\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_l10n_to_pipe
 *	Write a L10N structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	l10n		- L10N to write to stream.
 * Return:
 *	0		- Successfully wrote L10N to stream.
 *	-1		- Failed to write L10N to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_l10n_to_pipe(FILE *fp, L10N *l10n)
{
	if (l10n->l10n_package) {
		/*
		 * l10n_package is a modinfo that lives in the Product's
		 * p_packages list.  We just write out the m_pkgid here
		 * and the reader will have to find the real modinfo based
		 * on the m_pkgid.
		 */
		(void) fprintf(fp, "l10n_package=%s\n",
			l10n->l10n_package->m_pkgid);
	}
	if (l10n->l10n_next) {
		(void) fprintf(fp, "L10N_L10N_NEXT\n");
		if (write_l10n_to_pipe(fp, l10n->l10n_next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_L10N\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_pkgslocalized_to_pipe
 *	Write a PkgsLocalized structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	p		- PkgsLocalized to write to stream.
 * Return:
 *	0		- Successfully wrote PkgsLocalized to stream.
 *	-1		- Failed to write PkgsLocalized to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_pkgslocalized_to_pipe(FILE *fp, PkgsLocalized *p)
{
	if (p->pkg_lclzd) {
		/*
		 * pkg_lclzd is a modinfo that lives in the Product's
		 * p_packages list.  We just write out the m_pkgid here
		 * and the reader will have to find the real modinfo based
		 * on the m_pkgid.
		 */
		(void) fprintf(fp, "pkg_lclzd=%s\n", p->pkg_lclzd->m_pkgid);
	}
	if (p->next) {
		(void) fprintf(fp, "PKGSLOCALIZED_NEXT\n");
		if (write_pkgslocalized_to_pipe(fp, p->next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_PKGSLOCALIZED\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_modinfo_node_to_pipe
 *	Write a Node structure and all of its constituent members to a
 *	file stream.  The Node structure has data of type Modinfo.
 * Parameters:
 *	fp		- FILE string to write to
 *	n		- Node to write to stream.
 *	follow_link	- flag to specify whether or not to write
 *			this Nodes's next Node to the pipe.
 * Return:
 *	0		- Successfully wrote Node to stream.
 *	-1		- Failed to write Node to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_modinfo_node_to_pipe(FILE *fp, Node *n, boolean_t follow_link)
{
	Modinfo *mi;

	if (n->key)
		(void) fprintf(fp, "key=%s\n", n->key);
	if ((mi = (Modinfo *)n->data) != NULL) {
		(void) fprintf(fp, "MODINFO_NODE_DATA\n");
		if (write_modinfo_to_pipe(fp, mi) != 0)
			return (-1);
	}

	/*
	 * Skipping delproc, the reading function will find the
	 * delproc function pointer for a modinfo node and set
	 * the pointer accordingly.
	 */

	if (follow_link) {
		if (n->next) {
			(void) fprintf(fp, "MODINFO_NODE_NEXT\n");
			if (write_modinfo_node_to_pipe(fp, n->next,
			    follow_link) != 0)
				return (-1);
		}
	}

	(void) fprintf(fp, "END_MODINFO_NODE\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_module_node_to_pipe
 *	Write a Node structure and all of its constituent members to a
 *	file stream.  The Node structure has data of type Module.
 * Parameters:
 *	fp		- FILE string to write to
 *	n		- Node to write to stream.
 *	follow_link	- flag to specify whether or not to write
 *			this Nodes's next Node to the pipe.
 * Return:
 *	0		- Successfully wrote Node to stream.
 *	-1		- Failed to write Node to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_module_node_to_pipe(FILE *fp, Node *n, boolean_t follow_link,
    boolean_t follow_sub)
{
	Module *mod;

	if (n->key)
		(void) fprintf(fp, "key=%s\n", n->key);
	if ((mod = (Module *)n->data) != NULL) {
		(void) fprintf(fp, "MODULE_NODE_DATA\n");
		if (write_module_to_pipe(fp, mod, follow_sub) != 0)
			return (-1);
	}

	/*
	 * Skipping delproc, the reading function will find the
	 * delproc function pointer for a module node and set
	 * the pointer accordingly.
	 */

	if (follow_link) {
		if (n->next) {
			(void) fprintf(fp, "MODULE_NODE_NEXT\n");
			if (write_module_node_to_pipe(fp, n->next,
			    follow_link, follow_sub) != 0)
				return (-1);
		}
	}

	(void) fprintf(fp, "END_MODULE_NODE\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_depend_to_pipe
 *	Write a Depend structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	depend		- Depend to write to stream.
 * Return:
 *	0		- Successfully wrote Depend to stream.
 *	-1		- Failed to write Depend to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_depend_to_pipe(FILE *fp, Depend *depend)
{
	if (depend->d_pkgid)
		(void) fprintf(fp, "d_pkgid=%s\n", depend->d_pkgid);
	if (depend->d_pkgidb)
		(void) fprintf(fp, "d_pkgidb=%s\n", depend->d_pkgidb);
	if (depend->d_version)
		(void) fprintf(fp, "d_version=%s\n", depend->d_version);
	if (depend->d_arch)
		(void) fprintf(fp, "d_arch=%s\n", depend->d_arch);
	if (depend->d_zname)
		(void) fprintf(fp, "d_zname=%s\n", depend->d_zname);
	(void) fprintf(fp, "d_type=%d\n", depend->d_type);
	if (depend->d_next) {
		(void) fprintf(fp, "DEPEND_D_NEXT\n");
		if (write_depend_to_pipe(fp, depend->d_next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_DEPEND\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_filepp_to_pipe
 *	Write a array of File structures to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	f		- Pointer to an array of Files to write to stream.
 * Return:
 *	0		- Successfully wrote File ** to stream.
 *	-1		- Failed to write File ** to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_filepp_to_pipe(FILE *fp, File **f)
{
	int	n_files = 0;

	while (f[n_files] != NULL) {
		(void) fprintf(fp, "FILEPP_FILE\n");
		if (write_file_to_pipe(fp, f[n_files++]) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_FILEPP\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_file_to_pipe
 *	Write a File structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	f		- File to write to stream.
 * Return:
 *	0		- Successfully wrote File to stream.
 *	-1		- Failed to write File to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_file_to_pipe(FILE *fp, File *f)
{
	if (f->f_path != NULL)
		(void) fprintf(fp, "f_path=%s\n", f->f_path);
	if (f->f_name != NULL)
		(void) fprintf(fp, "f_name=%s\n", f->f_name);
	(void) fprintf(fp, "f_type=%d\n", f->f_type);
	if (f->f_args != NULL)
		(void) fprintf(fp, "f_args=%s\n", f->f_args);

	/* Skipping f_data */

	(void) fprintf(fp, "END_FILE\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_pkg_hist_to_pipe
 *	Write a pkg_hist structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	ph		- pkg_hist to write to stream.
 * Return:
 *	0		- Successfully wrote pkg_hist to stream.
 *	-1		- Failed to write pkg_hist to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_pkg_hist_to_pipe(FILE *fp, struct pkg_hist *ph)
{
	if (ph->prod_rm_list)
		(void) fprintf(fp, "prod_rm_list=%s\n", ph->prod_rm_list);
	if (ph->replaced_by)
		(void) fprintf(fp, "replaced_by=%s\n", ph->replaced_by);
	if (ph->deleted_files)
		(void) fprintf(fp, "deleted_files=%s\n", ph->deleted_files);
	if (ph->cluster_rm_list)
		(void) fprintf(fp, "cluster_rm_list=%s\n", ph->cluster_rm_list);
	if (ph->ignore_list)
		(void) fprintf(fp, "ignore_list=%s\n", ph->ignore_list);
	(void) fprintf(fp, "to_be_removed=%d\n", ph->to_be_removed);
	(void) fprintf(fp, "needs_pkgrm=%d\n", ph->needs_pkgrm);
	(void) fprintf(fp, "basedir_change=%d\n", ph->basedir_change);
	(void) fprintf(fp, "ref_count=%d\n", ph->ref_count);

	if (ph->hist_next) {
		(void) fprintf(fp, "PKG_HIST_HIST_NEXT\n");
		if (write_pkg_hist_to_pipe(fp, ph->hist_next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_PKG_HIST\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_filediff_to_pipe
 *	Write a filediff structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	diff		- filediff to write to stream.
 *	follow_link	- flag to specify whether or not to attempt to
 *			write out this filediff's next member.
 * Return:
 *	0		- Successfully wrote filediff to stream.
 *	-1		- Failed to write filediff to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_filediff_to_pipe(FILE *fp, struct filediff *diff, boolean_t follow_link)
{
	if (diff->pkg_info_ptr) {
		(void) fprintf(fp, "FILEDIFF_PKG_INFO_PTR\n");
		if (write_pkg_info_to_pipe(fp, diff->pkg_info_ptr) != 0)
			return (-1);
	}

	/*
	 * owning_pkg
	 *
	 * NOTE: owning_pkg is not piped across because it is a
	 * reference pointer to the modinfo of which this filediff belongs.
	 * As the reader on the other side of the pipe reads a modinfo,
	 * it will set the modinfo's constituent filediff's owning_pkgs to
	 * itself.
	 */

	if (diff->replacing_pkg) {
		/*
		 * replacing_pkg is a reference pointer to the
		 * modinfo for the package in the new media's product
		 * p_package list.  We pass the package's id, and the
		 * reader of this data on the other side of the pipe
		 * must find the pointer to that package's modinfo
		 */
		(void) fprintf(fp, "replacing_pkg=%s\n",
		    diff->replacing_pkg->m_pkgid);
	}

	(void) fprintf(fp, "diff_flags=%d\n", diff->diff_flags);
	if (diff->linkptr)
		(void) fprintf(fp, "linkptr=%s\n", diff->linkptr);
	if (diff->link_found)
		(void) fprintf(fp, "link_found=%s\n", diff->link_found);
	(void) fprintf(fp, "majmin=%lu\n", (ulong) diff->majmin);
	(void) fprintf(fp, "act_mode=%lu\n", (ulong) diff->act_mode);
	(void) fprintf(fp, "act_uid=%ld\n", (long)diff->act_uid);
	(void) fprintf(fp, "act_gid=%ld\n", (long)diff->act_gid);
	if (diff->exp_type)
		(void) fprintf(fp, "exp_type=%c\n", diff->exp_type);
	if (diff->actual_type)
		(void) fprintf(fp, "actual_type=%c\n", diff->actual_type);
	if (strlen(diff->pkgclass) > 0)
		(void) fprintf(fp, "pkgclass=%s\n", diff->pkgclass);
	if (strlen(diff->component_path) > 0)
		(void) fprintf(fp, "component_path=%s\n", diff->component_path);
	if (diff->diff_next && follow_link) {
		(void) fprintf(fp, "FILEDIFF_DIFF_NEXT\n");
		if (write_filediff_to_pipe(fp, diff->diff_next, 1) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_FILEDIFF\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_patch_num_to_pipe
 *	Write a patch_num structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	patchnum	- patch_num to write to stream.
 * Return:
 *	0		- Successfully wrote patch_num to stream.
 *	-1		- Failed to write patch_num to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_patch_num_to_pipe(FILE *fp, struct patch_num *patchnum)
{
	if (patchnum->patch_num_id)
		(void) fprintf(fp, "patch_num_id=%s\n", patchnum->patch_num_id);
	if (patchnum->patch_num_rev_string)
		(void) fprintf(fp, "patch_num_rev_string=%s\n",
		    patchnum->patch_num_rev_string);
	(void) fprintf(fp, "patch_num_rev=%u\n", patchnum->patch_num_rev);
	if (patchnum->next) {
		(void) fprintf(fp, "PATCH_NUM_NEXT\n");
		if (write_patch_num_to_pipe(fp, patchnum->next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_PATCH_NUM\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_stringlist_to_pipe
 *	Write a StringList structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	sl		- StringList to write to stream.
 * Return:
 *	0		- Successfully wrote StringList to stream.
 *	-1		- Failed to write StringList to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_stringlist_to_pipe(FILE *fp, StringList *sl)
{
	StringList	*n;

	if (sl->string_ptr)
		(void) fprintf(fp, "string_ptr=%s\n", sl->string_ptr);

	for (n = sl->next; n; n = n->next) {
		if (n->string_ptr)
			(void) fprintf(fp, "string_ptr=%s\n", n->string_ptr);
	}

	(void) fprintf(fp, "END_STRINGLIST\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_contentsrecord_to_pipe
 *	Write a ContentsRecord structure and all of its constituent members
 *	to a file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	cr		- ContentsRecord to write to stream.
 * Return:
 *	0		- Successfully wrote ContentsRecord to stream.
 *	-1		- Failed to write ContentsRecord to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_contentsrecord_to_pipe(FILE *fp, ContentsRecord *cr)
{
	(void) fprintf(fp, "ctsrec_idx=%d\n", cr->ctsrec_idx);
	(void) fprintf(fp, "CONTENTSRECORD_CTSREC_BRKDN\n");
	if (write_contentsbrkdn_to_pipe(fp, &(cr->ctsrec_brkdn)) != 0)
		return (-1);

	if (cr->next) {
		(void) fprintf(fp, "CONTENTSRECORD_NEXT\n");
		if (write_contentsrecord_to_pipe(fp, cr->next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_CONTENTSRECORD\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_contentsbrkdn_to_pipe
 *	Write a ContentsBrkdn structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	cb		- ContentsBrkdn to write to stream.
 * Return:
 *	0		- Successfully wrote ContentsBrkdn to stream.
 *	-1		- Failed to write ContentsBrkdn to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_contentsbrkdn_to_pipe(FILE *fp, ContentsBrkdn *cb)
{
	(void) fprintf(fp, "contents_packaged=%lu\n", cb->contents_packaged);
	(void) fprintf(fp, "contents_nonpkg=%lu\n", cb->contents_nonpkg);
	(void) fprintf(fp, "contents_products=%lu\n", cb->contents_products);
	(void) fprintf(fp, "contents_devfs=%lu\n", cb->contents_devfs);
	(void) fprintf(fp, "contents_savedfiles=%lu\n",
	    cb->contents_savedfiles);
	(void) fprintf(fp, "contents_pkg_ovhd=%lu\n", cb->contents_pkg_ovhd);
	(void) fprintf(fp, "contents_patch_ovhd=%lu\n",
	    cb->contents_patch_ovhd);
	(void) fprintf(fp, "contents_inodes_used=%lu\n",
	    cb->contents_inodes_used);

	(void) fprintf(fp, "END_CONTENTSBRKDN\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_charpp_to_pipe
 *	Write a array of strings to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	sa		- Array of strings to write to stream.
 * Return:
 *	0		- Successfully wrote char ** to stream.
 *	-1		- Failed to write char ** to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_charpp_to_pipe(FILE *fp, char **sa)
{
	int	n_strs = 0;

	while (sa[n_strs] != NULL) {
		(void) fprintf(fp, "string=%s\n", sa[n_strs++]);
	}

	(void) fprintf(fp, "END_CHARPP\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_arch_to_pipe
 *	Write a Arch structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	arch		- Arch to write to stream.
 * Return:
 *	0		- Successfully wrote Arch to stream.
 *	-1		- Failed to write Arch to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_arch_to_pipe(FILE *fp, Arch *arch)
{
	if (arch->a_arch)
		(void) fprintf(fp, "a_arch=%s\n", arch->a_arch);
	(void) fprintf(fp, "a_selected=%d\n", arch->a_selected);
	(void) fprintf(fp, "a_loaded=%d\n", arch->a_loaded);
	if (arch->a_platforms) {
		(void) fprintf(fp, "ARCH_A_PLATFORMS\n");
		if (write_stringlist_to_pipe(fp, arch->a_platforms) != 0)
			return (-1);
	}
	if (arch->a_next) {
		(void) fprintf(fp, "ARCH_A_NEXT\n");
		if (write_arch_to_pipe(fp, arch->a_next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_ARCH\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_modinfo_list_to_pipe
 *	Write a List structure and all of its constituent members to a
 *	file stream.  The List structure contains Nodes that have data
 *	members of type Modinfo.
 * Parameters:
 *	fp		- FILE string to write to
 *	list		- List to write to stream.
 * Return:
 *	0		- Successfully wrote List to stream.
 *	-1		- Failed to write List to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_modinfo_list_to_pipe(FILE *fp, List *list)
{
	Node	*head, *n;

	if (list->list) {
		head = list->list;
		n = head->next;
		while (n && (n != head)) {
			(void) fprintf(fp, "LIST_MODINFO_NODE\n");
			if (write_modinfo_node_to_pipe(fp, n, B_FALSE) != 0)
				return (-1);
			n = n->next;
		}
	}

	(void) fprintf(fp, "END_MODINFO_LIST\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_module_list_to_pipe
 *	Write a List structure and all of its constituent members to a
 *	file stream.  The List structure contains Nodes that have data
 *	members of type Module.
 * Parameters:
 *	fp		- FILE string to write to
 *	list		- List to write to stream.
 * Return:
 *	0		- Successfully wrote List to stream.
 *	-1		- Failed to write List to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_module_list_to_pipe(FILE *fp, List *list)
{
	Node	*head, *n;

	if (list->list) {
		head = list->list;
		n = head->next;
		while (n && (n != head)) {
			(void) fprintf(fp, "LIST_MODULE_NODE\n");
			if (write_module_node_to_pipe(fp, n, B_FALSE,
			    B_TRUE) != 0)
				return (-1);
			n = n->next;
		}
	}

	(void) fprintf(fp, "END_MODULE_LIST\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_pkg_info_to_pipe
 *	Write a pkg_info structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	pi		- pkg_info to write to stream.
 * Return:
 *	0		- Successfully wrote pkg_info to stream.
 *	-1		- Failed to write pkg_info to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_pkg_info_to_pipe(FILE *fp, struct pkg_info *pi)
{
	if (pi->name)
		(void) fprintf(fp, "name=%s\n", pi->name);
	if (pi->arch)
		(void) fprintf(fp, "arch=%s\n", pi->arch);
	if (pi->next) {
		(void) fprintf(fp, "PKG_INFO_NEXT\n");
		if (write_pkg_info_to_pipe(fp, pi->next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_PKG_INFO\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_sw_config_to_pipe
 *	Write a SW_config structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	sw		- SW_config to write to stream.
 * Return:
 *	0		- Successfully wrote SW_config to stream.
 *	-1		- Failed to write SW_config to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_sw_config_to_pipe(FILE *fp, SW_config *sw)
{
	if (sw->sw_cfg_name)
		(void) fprintf(fp, "sw_cfg_name=%s\n", sw->sw_cfg_name);
	if (sw->sw_cfg_members) {
		(void) fprintf(fp, "SW_CONFIG_SW_CFG_MEMBERS\n");
		if (write_stringlist_to_pipe(fp, sw->sw_cfg_members) != 0)
			return (-1);
	}
	(void) fprintf(fp, "sw_cfg_auto=%d\n", sw->sw_cfg_auto);
	if (sw->next) {
		(void) fprintf(fp, "SW_CONFIG_NEXT\n");
		if (write_sw_config_to_pipe(fp, sw->next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_SW_CONFIG\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_hw_config_to_pipe
 *	Write a HW_config structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	hw		- HW_config to write to stream.
 * Return:
 *	0		- Successfully wrote HW_config to stream.
 *	-1		- Failed to write HW_config to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_hw_config_to_pipe(FILE *fp, HW_config *hw)
{
	if (hw->hw_node)
		(void) fprintf(fp, "hw_node=%s\n", hw->hw_node);
	if (hw->hw_testprog)
		(void) fprintf(fp, "hw_testprog=%s\n", hw->hw_testprog);
	if (hw->hw_testarg)
		(void) fprintf(fp, "hw_testarg=%s\n", hw->hw_testarg);
	if (hw->hw_support_pkgs) {
		(void) fprintf(fp, "HW_CONFIG_HW_SUPPORT_PKGS\n");
		if (write_stringlist_to_pipe(fp, hw->hw_support_pkgs) != 0)
			return (-1);
	}
	if (hw->next) {
		(void) fprintf(fp, "HW_CONFIG_NEXT\n");
		if (write_hw_config_to_pipe(fp, hw->next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_HW_CONFIG\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_platgroup_to_pipe
 *	Write a PlatGroup structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	pg		- PlatGroup to write to stream.
 * Return:
 *	0		- Successfully wrote PlatGroup to stream.
 *	-1		- Failed to write PlatGroup to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_platgroup_to_pipe(FILE *fp, PlatGroup *pg)
{
	if (pg->pltgrp_name)
		(void) fprintf(fp, "pltgrp_name=%s\n", pg->pltgrp_name);
	if (pg->pltgrp_members) {
		(void) fprintf(fp, "PLATGROUP_PLTGRP_MEMBERS\n");
		if (write_platform_to_pipe(fp, pg->pltgrp_members) != 0)
			return (-1);
	}
	if (pg->pltgrp_config) {
		(void) fprintf(fp, "PLATGROUP_PLTGRP_CONFIG\n");
		if (write_sw_config_to_pipe(fp, pg->pltgrp_config) != 0)
			return (-1);
	}
	if (pg->pltgrp_all_config) {
		(void) fprintf(fp, "PLATGROUP_PLTGRP_ALL_CONFIG\n");
		if (write_sw_config_to_pipe(fp, pg->pltgrp_all_config) != 0)
			return (-1);
	}
	if (pg->pltgrp_isa)
		(void) fprintf(fp, "pltgrp_isa=%s\n", pg->pltgrp_isa);
	(void) fprintf(fp, "pltgrp_export=%d\n", pg->pltgrp_export);
	if (pg->next) {
		(void) fprintf(fp, "PLATGROUP_NEXT\n");
		if (write_platgroup_to_pipe(fp, pg->next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_PLATGROUP\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_platform_to_pipe
 *	Write a Platform structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	pf		- Platform to write to stream.
 * Return:
 *	0		- Successfully wrote Platform to stream.
 *	-1		- Failed to write Platform to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_platform_to_pipe(FILE *fp, Platform *pf)
{
	if (pf->plat_name)
		(void) fprintf(fp, "plat_name=%s\n", pf->plat_name);
	if (pf->plat_uname_id)
		(void) fprintf(fp, "plat_uname_id=%s\n", pf->plat_uname_id);
	if (pf->plat_machine)
		(void) fprintf(fp, "plat_machine=%s\n", pf->plat_machine);
	if (pf->plat_group)
		(void) fprintf(fp, "plat_group=%s\n", pf->plat_group);
	if (pf->plat_config) {
		(void) fprintf(fp, "PLATFORM_PLAT_CONFIG\n");
		if (write_sw_config_to_pipe(fp, pf->plat_config) != 0)
			return (-1);
	}
	if (pf->plat_all_config) {
		(void) fprintf(fp, "PLATFORM_PLAT_ALL_CONFIG\n");
		if (write_sw_config_to_pipe(fp, pf->plat_all_config) != 0)
			return (-1);
	}
	if (pf->plat_isa)
		(void) fprintf(fp, "plat_isa=%s\n", pf->plat_isa);
	if (pf->next) {
		(void) fprintf(fp, "PLATFORM_NEXT\n");
		if (write_platform_to_pipe(fp, pf->next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_PLATFORM\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_patch_to_pipe
 *	Write a patch structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	p		- patch to write to stream.
 * Return:
 *	0		- Successfully wrote patch to stream.
 *	-1		- Failed to write patch to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_patch_to_pipe(FILE *fp, struct patch *p)
{
	if (p->patchid)
		(void) fprintf(fp, "patchid=%s\n", p->patchid);
	(void) fprintf(fp, "removed=%d\n", p->removed);
	if (p->patchpkgs) {
		(void) fprintf(fp, "PATCH_PATCHPKGS\n");
		if (write_patchpkg_to_pipe(fp, p->patchpkgs) != 0)
			return (-1);
	}
	if (p->next) {
		(void) fprintf(fp, "PATCH_NEXT\n");
		if (write_patch_to_pipe(fp, p->next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_PATCH\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_patchpkg_to_pipe
 *	Write a patchpkg structure and all of its constituent members to a
 *	file stream.
 * Parameters:
 *	fp		- FILE string to write to
 *	pp		- patchpkg to write to stream.
 * Return:
 *	0		- Successfully wrote patchpkg to stream.
 *	-1		- Failed to write patchpkg to stream.
 * Status:
 * 	semi-private (internal library use only)
 */
int
write_patchpkg_to_pipe(FILE *fp, struct patchpkg *pp)
{
	if (pp->pkgmod) {
		/*
		 * pkgmod is a reference pointer to a modinfo that already
		 * exists in a package modinfo's m_next_patch list, hence we
		 * don't pipe it across.  We send only the modinfo's m_pkgid.
		 */
		(void) fprintf(fp, "patchpkg_mod=%s\n", pp->pkgmod->m_pkgid);
	}
	if (pp->next) {
		(void) fprintf(fp, "PATCHPKG_NEXT\n");
		if (write_patchpkg_to_pipe(fp, pp->next) != 0)
			return (-1);
	}

	(void) fprintf(fp, "END_PATCHPKG\n");
	(void) fflush(fp);
	return (0);
}

/*
 * write_newmedia_pkgovhd_to_pipe()
 *	Pipe new package information collected from within zone
 *	to the parent, which must file it
 *	for each package in module, pipes spooled size, overhead size,
 *	contents values
 * Parameters:
 *	fp	- pipe file descriptor
 *	mod	- Module corresponding to the zone
 * Return:
 * Status:
 *	private
 */
void
write_newmedia_pkgovhd_to_pipe(FILE *fp, Module *mod)
{
	Module	*newmedia;
	Node	*n;
	Modinfo *i, *j;
	List	*l;

	/* find newmedia pointer */
	newmedia = get_newmedia();

	/* use newmedia information specifically pertaining to mod */
	load_view(newmedia->sub, mod);

	(void) fprintf(fp, "NEWMEDIA_PKGOVHD\n"); /* opening tag */
	/* cycle through new packages for mod */
	l = newmedia->sub->info.prod->p_packages;
	for (n = l->list->next; n != NULL && n != l->list; n = n->next) {
		/* emulates walk_upg_final_chk */
		for (i = (Modinfo *)n->data;
		    i != (Modinfo *) NULL;
		    i = next_inst(i))
			for (j = i; j != (Modinfo *) NULL; j = next_patch(j))
				if (meets_reqs(j)) {
					/* pipe back */
					(void) fprintf(fp, "m_pkgid=%s\n",
					    j->m_pkgid);
					if (j->m_spooled_size != 0)
						(void) fprintf(fp,
						    "m_spooled_size=%lu\n",
						    j->m_spooled_size);
					(void) fprintf(fp, "m_pkgid=%s\n",
					    j->m_pkgid);
					(void) fprintf(fp, "m_fs_usage\n");
					if (write_contentsrecord_to_pipe(fp,
					    j->m_fs_usage) != 0)
						return;
					(void) fprintf(fp,
					    "m_pkgovhd_size=%lu\n",
					    (ulong) j->m_pkgovhd_size);
				}
	}
	(void) fprintf(fp, "END_NEWMEDIA_PKGOVHD\n"); /* closing tag */
}

/*
 * read_newmedia_pkgovhd_from_pipe()
 *	For each new package in module located in child zone,
 *	files spooled size, overhead size, contents values
 * Parameters:
 *	fp:	file descriptor for pipe
 * Return:
 *	spmi standard error return code - 0 = success
 * Status:
 *	private
 * Globals modified:
 *	mi->m_fs_usage, mi->m_pkgovhd_size, mi->m_spooled_size
 */
int
read_newmedia_pkgovhd_from_pipe(FILE *fp)
{
	char		pkgid[MAXPKGNAME_LENGTH] = {'\0'};
	char		pkginst[MAXPKGNAME_LENGTH] = {'\0'};
	char		patchid[MAXPKGNAME_LENGTH] = {'\0'};
	Module		*newmedia;
	Node		*n;
	Modinfo		*mi;
	int		err = 0;
	char		buf[BUFSIZ];

	/* Grab newmedia pointer and service shared with server info. */
	newmedia = get_newmedia();

	/* read newmedia package overhead data */
	while (fgetspipe(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (buf[0] == '#')
			continue;
		if (strcmp(buf, "NEWMEDIA_PKGOVHD") == 0) {
			pkgid[0] = pkginst[0] = patchid[0] = '\0';
			/* marker - just continue */
		} else if (STRNCMPC(buf, "m_pkgid") == 0) {
			(void) strlcpy(pkgid, get_value(buf, '='),
			    MAXPKGNAME_LENGTH);

			mi = NULL;

			(void) strlcpy(patchid, get_value(buf, '='),
			    MAXPKGNAME_LENGTH);
			if (streq("NULL", patchid)) {
				patchid[0] = '\0';
			}
			/* replicating logic of walk_upg_final_chk */
			if ((n = findnode(newmedia->sub->info.prod->p_packages,
			    pkgid)) == NULL) {
				err = SP_PIPE_ERR_READ_FINDNODE;
				goto done;
			}
			if ((mi = (Modinfo *)n->data) == NULL) {
				err = SP_PIPE_ERR_READ_FINDNODE;
				goto done;
			}
		} else if (STRNCMPC(buf, "m_fs_usage") == 0) {
			if (mi->m_fs_usage) { /* free old contents record */
				ContentsRecord *cr = mi->m_fs_usage, *pnext;
				while (cr != NULL) {
					pnext = cr->next;
					free(cr);
					cr = pnext;
				}
			}
			mi->m_fs_usage = read_contentsrecord_from_pipe(fp);
			if (mi->m_fs_usage == NULL) {
				err = SP_PIPE_ERR_READ_CONTENTSRECORD;
				break;
			}
		} else if (STRNCMPC(buf, "m_pkgovhd_size") == 0) {
			if (sscanf(get_value(buf, '='), "%lu",
			    &(mi->m_pkgovhd_size)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (STRNCMPC(buf, "m_spooled_size") == 0) {
			if (sscanf(get_value(buf, '='), "%ld",
			    &(mi->m_spooled_size)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
		} else if (strcmp(buf, "END_NEWMEDIA_PKGOVHD") == 0)
			break;
	}

done:	if (err != 0) {
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading newmedia pkgovhd: %d (%s)"), err,
		    buf ? buf : "NULL");
	}
	return (err);
}

/*
 * write_prod_pkgovhd_to_pipe()
 *	Adds space for /var/sadm/pkg/<pkg>'s we know about.
 *	pipe pkg overhead product data collected from non-global zone
 *		to the parent, which must file it for each package, instance,
 *		and patch respectively in module
 * Parameters:
 *	fp	- pipe file descriptor
 *	mod	- Module corresponding to the zone
 * Return:
 * Status:
 *	private
 */
void
write_prod_pkgovhd_to_pipe(FILE *fp, Module *mod)
{
	Product	*prod1;
	Node	*n;
	Modinfo *i, *j;
	List	*l;

	(void) fprintf(fp, "PROD_PKGOVHD\n");
	prod1 = mod->sub->info.prod;
	l = prod1->p_packages;
	/* for all packages */
	for (n = l->list->next; n != NULL && n != l->list; n = n->next) {
		/* for main package any instances */
		for (i = (Modinfo *)n->data;
		    i != (Modinfo *) NULL;
		    i = next_inst(i)) {
			if (i->m_shared == NOTDUPLICATE &&
			    !(i->m_flags & IS_UNBUNDLED_PKG))
				/* for each patch */
				for (j = i; j != (Modinfo *) NULL;
				    j = next_patch(j)) {
					if (is_child_zone_context &&
					    !j->m_pkgovhd_size)
						continue;
					/* emulates walk_upg_final_chk_pkgdir */
					/* emulates compute_pkg_ovhd */
					(void) fprintf(fp, "m_pkgid=%s\n",
					    j->m_pkgid);
					if (j->m_pkginst != NULL)
						(void) fprintf(fp,
						    "m_pkginst=%s\n",
						    j->m_pkginst);
					if (j->m_patchid != NULL)
						(void) fprintf(fp,
						    "m_patchid=%s\n",
						    j->m_patchid);
					(void) fprintf(fp,
					    "m_pkgovhd_size=%lu\n",
					    (ulong) j->m_pkgovhd_size);
				}
		}
	}
	(void) fprintf(fp, "END_PROD_PKGOVHD\n");
}

/*
 * read_prod_pkgovhd_from_pipe()
 *	Read the space for the /var/sadm/pkg/<pkginst> directories (existing)
 *	from the pipe
 * Parameters:
 *	fp:	file descriptor for pipe
 *	mod:	zone module
 * Return:
 *	spmi standard error return code - 0 = success
 * Status:
 *	private
 * Globals modified:
 *	for each package in /var/sadm/pkg/<pkginst> directories in child zone,
 *	files mi->m_pkgovhd_size
 */
int
read_prod_pkgovhd_from_pipe(FILE *fp, Module *mod)
{
	char		pkgid[MAXPKGNAME_LENGTH] = {'\0'};
	char		pkginst[MAXPKGNAME_LENGTH] = {'\0'};
	char		patchid[MAXPKGNAME_LENGTH] = {'\0'};
	Node		*n;
	Modinfo		*mi, *minst, *mpatch;
	int		err = 0;
	char		buf[BUFSIZ];
	List		*l;

	/* read module file usage and pkg overhead data */
	while (fgetspipe(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (strcmp(buf, "END_PROD_PKGOVHD") == 0)
			break;
		if (STRNCMPC(buf, "m_pkginst=") == 0) {
			(void) strlcpy(pkginst, get_value(buf, '='),
			    MAXPKGNAME_LENGTH);
		} else if (STRNCMPC(buf, "m_patchid=") == 0) {
			(void) strlcpy(patchid, get_value(buf, '='),
			    MAXPKGNAME_LENGTH);
		} else if (STRNCMPC(buf, "m_pkgid=") == 0) {
			(void) strlcpy(pkgid, get_value(buf, '='),
			    MAXPKGNAME_LENGTH);
		} else if (STRNCMPC(buf, "m_pkgovhd_size=") == 0) {
			/* find match on package instance */
			/* replicating logic of walk_upg_final_chk_pkgdir */
			mi = NULL;
			l = mod->sub->info.prod->p_packages;
			for (n = l->list->next;
			    n != NULL && n != l->list && !mi;
			    n = n->next) {
				for (minst = (Modinfo *)n->data;
				    minst && !mi;
				    minst = next_inst(minst)) {
					if (streq(pkgid, minst->m_pkgid)) {
						mi = minst;
						break;
					}
					for (mpatch = next_patch(minst);
					    mpatch && !mi;
					    mpatch = next_patch(mpatch))
						if (streq(pkgid,
						    mpatch->m_pkgid))
							mi = minst;
				}
			}
			if (mi == NULL) {
				err = SP_PIPE_ERR_NO_PROD_PKG_INST;
				break;
			/* file package overhead size */
			} else if (sscanf(get_value(buf, '='), "%lu",
			    &(mi->m_pkgovhd_size)) != 1) {
				err = SP_PIPE_ERR_READ_SSCANF_FAILED;
				break;
			}
			pkgid[0] = '\0';
			pkginst[0] = '\0';
			patchid[0] = '\0';
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading prod pkgovhd: %d (%s)"), err,
		    buf ? buf : "NULL");
	}
	return (err);
}

/*
 * write_FSspace_to_pipe()
 *	File system usage counters collected in child zone are written to pipe
 *	pipe
 * Parameters:
 *	fp:	file descriptor for pipe
 *	fs:	file system space sizes from zone
 * Return:
 *	void
 * Status:
 *	private
 */
void
write_FSspace_to_pipe(FILE *fp, FSspace *fs)
{
	(void) fprintf(fp, "fsp_mntpnt=%s\n", fs->fsp_mntpnt);
	(void) fprintf(fp, "fsp_flags=%d\n", fs->fsp_flags);
	(void) write_contentsbrkdn_to_pipe(fp, &(fs->fsp_cts));
	(void) fflush(fp);
}

/*
 * read_FSspace_from_pipe()
 *	file system usage counters collected from child zone are read from pipe
 *	and filed in the master file space table
 * Parameters:
 *	fp:	file descriptor for pipe
 *	zonePath:	root path of zone
 *	sp:	file system space information from zone
 * Return:
 *	non-zero error code if failure
 * Status:
 *	private
 */
int
read_FSspace_from_pipe(FILE *fp, char *zonePath, FSspace **sp)
{
	char		buf[BUFSIZ];
	char		mntpnt[MAXPATHLEN] = {'\0'};
	int		fsp_flags = 0;
	ContentsBrkdn	cb;
	int		err = 0;

	while (fgetspipe(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';
		if (STRNCMPC(buf, "fsp_mntpnt=") == 0) {
			(void) strncpy(mntpnt, get_value(buf, '='),
			    sizeof (mntpnt));
		} else if (STRNCMPC(buf, "fsp_flags=") == 0) {
			fsp_flags = atoi(get_value(buf, '='));
			/* represents end of entry - file FS info */
			if (read_contentsbrkdn_from_pipe(fp, &cb) != 0) {
				err = SP_PIPE_ERR_READ_CONTENTSBRKDN;
				break;
			}
			/* credit local zone to proper FS in global */
			record_FS_info(sp, zonePath, mntpnt, &cb, fsp_flags);
		} else if (streq(buf, "END_FSSPACE")) {
			break;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}

	if (err != 0) {
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading FSspace: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (err);
	}

	return (0);
}

/*
 * Name:	write_filediff_owning_pkg_to_pipe()
 * write a list of filediffs, providing owning_pkg (a Modinfo member)
 * extends write_filediff_to_pipe() (which does not supply owning_pkg)
 * must be read with read_filediff_owning_pkg_from_pipe
 * Parameters:
 *	fp: file descriptor for pipe
 *	diff_list: pointer to list of files that have changed
 * Returns:
 *	0 Success / -1 failure
 */
int
write_filediff_owning_pkg_to_pipe(FILE *fp, struct filediff *diff_list)
{
	struct filediff *diff;

	if (diff_list != NULL) {
		for (diff = diff_list; diff != NULL; diff = diff->diff_next) {
			/* write diffs one at a time */
			(void) fprintf(fp, "FILEDIFF\n");
			/* first write owning_pkg */
			if (diff->owning_pkg)
				(void) fprintf(fp, "owning_pkg=%s\n",
				    diff->owning_pkg->m_pkgid);
			/* write rest of filediff */
			if (write_filediff_to_pipe(fp, diff, 0) != 0)
				return (-1);
		}
	}
	return (0);
}

/*
 * Name:	read_filediff_owning_pkg_from_pipe()
 * read a list of filediffs, expecting owning_pkg (a Modinfo member)
 * extends read_filediff_from_pipe() (which does not supply owning_pkg)
 * diffs must be written with write_filediff_owning_pkg_to_pipe
 * It expects to first receive owning_pkg, then the rest of the filediff
 * Parameters:
 *	fp: file descriptor for pipe
 *	mod: zone module
 * Returns:
 *	0=Success, otherwise pipe read error code
 * Globals modified:
 *	mi->owning_pkg->m_filediff list appended
 */
int
read_filediff_owning_pkg_from_pipe(FILE *fp, Module *mod)
{
	struct filediff	*diff = NULL, *next_diff;
	char		owning_pkg[MAXPKGNAME_LENGTH];
	Modinfo		*mi, *minst, *mpatch;
	Node		*n;
	List		*l;
	int		err = 0;
	char		buf[BUFSIZ];
	struct filediff	**statpp;

	if (fgetspipe(buf, BUFSIZ, fp) == NULL) {
		err = SP_PIPE_ERR_READ_FILEDIFF;
		goto done;
	}
	if (STRNCMPC(buf, "owning_pkg=") == 0) {
		(void) strlcpy(owning_pkg, get_value(buf, '='),
		    MAXPKGNAME_LENGTH);
		diff = read_filediff_from_pipe(fp, B_FALSE);
		l = mod->sub->info.prod->p_packages;
		mi = NULL;
		for (n = l->list->next;
		    n != NULL && n != l->list && !mi;
		    n = n->next) {
			for (minst = (Modinfo *)n->data;
			    minst && !mi;
			    minst = next_inst(minst)) {
				if (streq(owning_pkg, minst->m_pkgid)) {
					mi = minst;
					break;
				}
				for (mpatch = next_patch(minst);
				    mpatch && !mi;
				    mpatch = next_patch(mpatch))
					if (streq(owning_pkg,
					    mpatch->m_pkgid)) {
						mi = minst;
						break;
					}
			}
		}

		if (mi == NULL) {
			err = SP_PIPE_ERR_READ_FINDNODE;
			goto done;
		}
		diff->owning_pkg = mi;

		statpp = &(diff->owning_pkg->m_filediff);
		while (*statpp != (struct filediff *)NULL)
			statpp = &((*statpp)->diff_next);
		*statpp = diff;
		diff->diff_next = NULL;
		for (; diff != NULL; diff = next_diff) {
			next_diff = diff->diff_next;

			statpp = &(diff->owning_pkg->m_filediff);
			while (*statpp != (struct filediff *)NULL)
				statpp = &((*statpp)->diff_next);
			*statpp = diff;
			diff->diff_next = NULL;
		}
	}

done:	if (err) {
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading zone filediff: %d (%s)"), err,
		    buf ? buf : "NULL");
		return (err);
	}
	return (0);
}

/*
 * write_zone_fs_analysis_to_pipe()
 * assorted information collected from zone is read from pipe and
 *	filed into file space, extra contents file space
 * Parameters:
 *	fd:	file descriptor for pipe
 *	mod:	non-global zone module
 *	istab:	extra contents from zone in file system struct
 *	fs_list:	file system sizes from zone
 * Return:
 *	void
 * Status:
 *	private
 */
int
write_zone_fs_analysis_to_pipe(FILE *fp, Module *mod, FSspace **istab,
    FSspace **fs_list, boolean_t first_pass)
{
	int l;

	if (first_pass) { /* once only */
		/* extra contents */
		(void) fprintf(fp, "FSSPACE_EXTRA\n");
		for (l = 0; istab[l]; l++)
			write_FSspace_to_pipe(fp, istab[l]);
		(void) fprintf(fp, "END_FSSPACE\n");

		/* file differences */
		if (write_real_modified_list_to_pipe(fp) != 0) {
			write_message(LOGSCR, WARNMSG, LEVEL0,
			    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure writing file difference list-zone module: %s"),
			    mod->info.media->med_dir);
			return (-1);
		}
	} /* tasks performed only once */

	/* mark newmedia use in zone */
	write_newmedia_pkgovhd_to_pipe(fp, mod);
	/* mark product package overhead */
	write_prod_pkgovhd_to_pipe(fp, mod);
	/* fs space used by zone */
	(void) fprintf(fp, "FSSPACE_ZONE\n");
	for (l = 0; fs_list[l]; l++)
		write_FSspace_to_pipe(fp, fs_list[l]);
	(void) fprintf(fp, "END_FSSPACE\n");

	return (0);
}

/*
 * read_zone_fs_analysis_from_pipe()
 * assorted information collected from zone is read from pipe and
 *	filed into file space, extra contents file space
 * Parameters:
 *	fd:	file descriptor for pipe
 *	mod:	non-global zone module
 *	istab:	extra contents from zone in file system struct
 *	fs_list:	file system sizes from zone
 *	dfp:	debug file descriptor
 * Return:
 *	err:	error code from pipe failure
 * Status:
 *	private
 */
int
read_zone_fs_analysis_from_pipe(FILE *fd, Module *mod, FSspace **istab,
    FSspace **fs_list, FILE *dfp)
{
	char	buf[BUFSIZ];
	int	err = 0;
	Module	*newmedia;

	if (get_trace_level() > 2)
		fgets_start_monitor(); /* monitor pipe input */

	/* Grab newmedia pointer and service shared with server info. */
	newmedia = get_newmedia();

	/* set view on module wrt to new media */
	load_view(newmedia->sub, mod);

	/* read child information independent of order */
	while (fgetspipe(buf, BUFSIZ, fd) != NULL) {
		buf[strlen(buf) - 1] = '\0';

		/* newmedia package overhead */
		if (strcmp(buf, "NEWMEDIA_PKGOVHD") == 0) {
			if ((err = read_newmedia_pkgovhd_from_pipe(fd)) != 0) {
				write_message(LOG, ERRMSG, LEVEL3,
				    dgettext("SUNW_INSTALL_SWLIB",
					"Failure reading install media data "
					"from zone: %d (%s)"),
				    err, mod->info.media->med_dir);
				goto done;
			}
		} else if (strcmp(buf, "PROD_PKGOVHD") == 0) {
			if ((err = read_prod_pkgovhd_from_pipe(fd, mod)) != 0) {
				write_message(LOG, ERRMSG, LEVEL3,
				    dgettext("SUNW_INSTALL_SWLIB",
					"Failure reading package overhead "
					"data from zone: %d (%s)"),
					err, mod->info.media->med_dir);
				goto done;
			}
		} else if (strcmp(buf, "FSSPACE_EXTRA") == 0) {
			if (get_trace_level() > 0)
				print_space_usage(dfp,
				    "Before loading zone extra contents",
				    istab);
			if ((err = read_FSspace_from_pipe(fd,
				    mod->info.media->med_dir, istab)) != 0) {
				write_message(LOG, ERRMSG, LEVEL3,
				    dgettext("SUNW_INSTALL_SWLIB",
					"Failure filesystem space "
					"data from zone: %d (%s)"),
					err, mod->info.media->med_dir);
				goto done;
			}
			if (get_trace_level() > 0)
				print_space_usage(dfp,
				    "After loading zone extra contents", istab);
		} else if (strcmp(buf, "FSSPACE_ZONE") == 0) {
			if (get_trace_level() > 0)
				print_space_usage(dfp,
				    "Before loading zone space", fs_list);
			if ((err = read_FSspace_from_pipe(fd,
				    mod->info.media->med_dir, fs_list)) != 0) {
				write_message(LOG, ERRMSG, LEVEL3,
				    dgettext("SUNW_INSTALL_SWLIB",
					"Failure filesystem space "
					"data from zone: %d (%s)"),
					err, mod->info.media->med_dir);
				goto done;
			}
			if (get_trace_level() > 0)
				print_space_usage(dfp,
				    "After loading zone space", fs_list);
		} else if (strcmp(buf, "FILEDIFF") == 0) {
			/*
			 * unlink the diff from the diff list
			 * link the diff to the owning package
			 */
			if ((err = read_real_modified_list_from_pipe(fd, mod))
			    != 0) {
				write_message(LOG, ERRMSG, LEVEL3,
				    dgettext("SUNW_INSTALL_SWLIB",
				    "Failure file differences "
				    "data from zone: %d (%s)"),
				    err, mod->info.media->med_dir);
				goto done;
			}
			mod->info.media->med_flags |= MODIFIED_FILES_FOUND;
		} else {
			/* NOT SUPPOSED TO HAPPEN */
			err = SP_PIPE_ERR_READ_INVALID_LINE;
			break;
		}
	}
	/* Set the view back to global root if it isn't already */
	if (get_current_view(newmedia->sub) != get_localmedia())
		load_local_view(newmedia->sub);

done:	if (err != 0)
		write_message(LOG, ERRMSG, LEVEL3,
		    dgettext("SUNW_INSTALL_SWLIB",
		    "Failure reading zone fs analysis: %d (%s)"), err,
		    buf ? buf : "NULL");
	fgets_stop_monitor();

	return (err);
}
/*
 * utility functions to monitor pipe usage
 */
static FILE *open_debug_pipe_file(char *oflags);
static FILE *monitor_fgets_fd = NULL;
/*
 * start pipe monitoring to file
 * to receive data, use fgetspipe instead of fgets
 */
void
fgets_start_monitor(void)
{
	static int first_time = 1;

	monitor_fgets_fd = open_debug_pipe_file(
		first_time ? "w":"a+");
	first_time = 0;
}
/*
 * works identically to fgets, which it calls
 * in addition, saves piped data to file
 * if enabled with fgets_start_monitor()
 */
char *
fgetspipe(char *buf, int bufsiz, FILE *fp)
{
	char *gotbuf;
	do {
		gotbuf = fgets(buf, bufsiz, fp);
		if (monitor_fgets_fd == NULL)
			return (gotbuf);
		if (gotbuf == NULL)
			(void) fprintf(monitor_fgets_fd, "EOF\n");
		else
			(void) fputs(buf, monitor_fgets_fd);
	} while (gotbuf != NULL && *gotbuf == '#');
	/* continue until EOF or while reading comments from pipe */
	return (gotbuf);
}
/* support function for pipe monitoring */
static FILE *
open_debug_pipe_file(char *oflags)
{
	char		*log_file = "/tmp/pipe.log";

	if (monitor_fgets_fd != NULL)
		return (monitor_fgets_fd);
	if (log_file != NULL) {
		monitor_fgets_fd = fopen(log_file, oflags);
		if (monitor_fgets_fd != NULL)
			(void) chmod(log_file, S_IRUSR | S_IWUSR |
			    S_IRGRP | S_IROTH);
	}
	return (monitor_fgets_fd);
}
/* support function for pipe monitoring */
void
fgets_stop_monitor()
{
	if (monitor_fgets_fd != NULL) {
		(void) fclose(monitor_fgets_fd);
		monitor_fgets_fd = NULL;
	}
}
/*
 * end of utility functions to monitor pipe usage
 */
/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */
