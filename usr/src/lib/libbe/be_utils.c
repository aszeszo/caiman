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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

/*
 * System includes
 */
#include <assert.h>
#include <errno.h>
#include <libintl.h>
#include <libnvpair.h>
#include <libzfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/vfstab.h>
#include <ctype.h>
#include <time.h>
#include <unistd.h>

#include "libbe.h"
#include "libbe_priv.h"

/* Private function prototypes */
static int update_dataset(char *, int, char *, char *);

/*
 * Global error printing
 */
boolean_t do_print = B_FALSE;

/* ********************************************************************	*/
/*			Public Functions				*/
/* ******************************************************************** */

/*
 * Function:	be_max_avail
 * Description:	Returns the available size for the zfs dataset passed in.
 * Parameters:
 *		dataset - The dataset we want to get the available space for.
 *		ret - The available size will be returned in this.
 * Returns:
 *		The error returned by the zfs get property function.
 * Scope:
 *		Public
 */
int
be_max_avail(char *dataset, uint64_t *ret)
{
	zfs_handle_t *zhp;
	int err = 0;

	/* Initialize libzfs handle */
	if (!be_zfs_init())
		return (1);

	zhp = zfs_open(g_zfs, dataset, ZFS_TYPE_DATASET);
	if (zhp == NULL) {
		/*
		 * The zfs_open failed return an error
		 */
		err = ENOENT;
	} else {
		err = be_maxsize_avail(zhp, ret);
	}
	if (zhp != NULL)
		zfs_close(zhp);
	be_zfs_fini();
	return (err);
}

/*
 * Function:	libbe_print_errors
 * Description:	Turns on/off error output for the library.
 * Parameter:
 *		set_do_print - Boolean that turns library error
 *			       printing on or off.
 * Returns:
 *		None
 * Scope:
 *		Public;
 */
void
libbe_print_errors(boolean_t set_do_print)
{
	do_print = set_do_print;
}

/* ********************************************************************	*/
/*			Semi-Private Functions				*/
/* ******************************************************************** */

/*
 * Function:	be_zfs_init
 * Description:	Initializes the libary global libzfs handle.
 * Parameters:
 *		None
 * Returns:
 *		B_TRUE - Success
 *		B_FALSE - Failure
 * Scope:
 *		Semi-private (library wide use only)
 */
boolean_t
be_zfs_init(void)
{
	be_zfs_fini();

	if ((g_zfs = libzfs_init()) == NULL) {
		be_print_err(gettext("be_zfs_init: failed to initialize ZFS "
		    "library\n"));
		return (B_FALSE);
	}

	return (B_TRUE);
}

/*
 * Function:	be_zfs_fini
 * Description:	Closes the library global libzfs handle if it currently open.
 * Parameter:
 *		None
 * Returns:
 *		None
 * Scope:
 *		Semi-private (library wide use only)
 */
void
be_zfs_fini(void)
{
	if (g_zfs)
		libzfs_fini(g_zfs);

	g_zfs = NULL;
}

/*
 * Function:	be_make_root_ds
 * Description:	Generate string for BE's root dataset given the pool
 *		it lives in and the BE name.
 * Parameters:
 *		zpool - pointer zpool name.
 *		be_name - pointer to BE name.
 *		be_root_ds - pointer to buffer to return BE root dataset in.
 *		be_root_ds_size - size of be_root_ds
 * Returns:
 *		None
 * Scope:
 *		Semi-private (library wide use only)
 */
void
be_make_root_ds(const char *zpool, const char *be_name, char *be_root_ds,
    int be_root_ds_size)
{
	(void) snprintf(be_root_ds, be_root_ds_size, "%s/%s/%s", zpool,
	    BE_CONTAINER_DS_NAME, be_name);
}

/*
 * Function:	be_make_container_ds
 * Description:	Generate string for the BE container dataset given a pool name.
 * Parameters:
 *		zpool - pointer zpool name.
 *		container_ds - pointer to buffer to return BE container
 *			dataset in.
 *		container_ds_size - size of container_ds
 * Returns:
 *		None
 * Scope:
 *		Semi-private (library wide use only)
 */
void
be_make_container_ds(const char *zpool,  char *container_ds,
    int container_ds_size)
{
	(void) snprintf(container_ds, container_ds_size, "%s/%s", zpool,
	    BE_CONTAINER_DS_NAME);
}

/*
 * Function:	be_make_name_from_ds
 * Description:	This function takes a dataset name and strips off the
 *		BE container dataset portion from the beginning.  The
 *		returned name is allocated in heap storage, so the caller
 *		is responsible for freeing it.
 * Parameters:
 *		dataset - dataset to get name from.
 * Returns:
 *		name of dataset relative to BE container dataset.
 *		NULL if dataset is not under a BE root dataset.
 * Scope:
 *		Semi-primate (library wide use only)
 */
char *
be_make_name_from_ds(const char *dataset)
{
	char	ds[ZFS_MAXNAMELEN];
	char	*tok = NULL;

	/* Tokenize dataset */
	(void) strlcpy(ds, dataset, sizeof (ds));

	/* First token is the pool name, could be anything. */
	if ((tok = strtok(ds, "/")) == NULL)
		return (NULL);

	/* Second token must be BE container dataset name */
	if ((tok = strtok(NULL, "/")) == NULL ||
	    strcmp(tok, BE_CONTAINER_DS_NAME) != 0)
		return (NULL);

	/* Return the remaining token if one exists */
	if ((tok = strtok(NULL, "")) == NULL)
		return (NULL);

	return (strdup(tok));
}

/*
 * Function:	be_maxsize_avail
 * Description:	Returns the available size for the zfs handle passed in.
 * Parameters:
 *		zhp - A pointer to the open zfs handle.
 *		ret - The available size will be returned in this.
 * Returns:
 *		The error returned by the zfs get property function.
 * Scope:
 *		Semi-private (library wide use only)
 */
int
be_maxsize_avail(zfs_handle_t *zhp, uint64_t *ret)
{
	return ((*ret = zfs_prop_get_int(zhp, ZFS_PROP_AVAILABLE)));
}

/*
 * Function:	be_append_grub
 * Description:	Appends an entry for a BE into the menu.lst.
 * Parameters:
 *		be_name - pointer to name of BE to add GRUB menu entry for.
 *		be_root_pool - pointer to name of pool BE lives in.
 *		boot_pool - Used if the pool containing the grub menu is
 *			    different than the one contaiing the BE. This
 *			    will normally be NULL.
 *		description - pointer to description of BE to be added in
 *			the title line for this BEs entry.
 * Returns:
 *		0 - Success
 *		1 - Failure
 * Scope:
 *		Semi-private (library wide use only)
 */
int
be_append_grub(char *be_name, char *be_root_pool, char *boot_pool,
    char *description)
{
	zfs_handle_t *zhp = NULL;
	char grub_file[MAXPATHLEN];
	char be_root_ds[MAXPATHLEN];
	char pool_mntpnt[MAXPATHLEN];
	char line[BUFSIZ];
	char title[MAXPATHLEN];
	boolean_t found_be = B_FALSE;
	FILE *grub_fp = NULL;

	if (be_name == NULL || be_root_pool == NULL)
		return (1);

	if (boot_pool == NULL)
		boot_pool = be_root_pool;

	if ((zhp = zfs_open(g_zfs, be_root_pool, ZFS_TYPE_DATASET)) == NULL) {
		be_print_err(gettext("be_append_grub: failed to open "
		    "pool dataset for %s\n"), be_root_pool);
		return (1);
	}

	(void) zfs_prop_get(zhp, ZFS_PROP_MOUNTPOINT, pool_mntpnt,
	    sizeof (pool_mntpnt), NULL, NULL, 0, B_FALSE);

	zfs_close(zhp);

	(void) snprintf(grub_file, sizeof (grub_file),
	    "%s/boot/grub/menu.lst", pool_mntpnt);

	be_make_root_ds(be_root_pool, be_name, be_root_ds, sizeof (be_root_ds));


	/*
	 * Iterate through menu first to make sure the BE doesn't already
	 * have an entry in the menu.
	 */
	grub_fp = fopen(grub_file, "r");
	if (grub_fp == NULL) {
		be_print_err(gettext("be_append_grub: failed "
		    "to open menu.lst file %s\n"), grub_file);
		return (1);
	}
	while (fgets(line, BUFSIZ, grub_fp)) {
		char *tok = strtok(line, " \t\r\n");

		if (tok == NULL || tok[0] == '#') {
			continue;
		} else if (strcmp(tok, "title") == 0) {
			if ((tok = strtok(NULL, "\n")) == NULL)
				(void) strlcpy(title, "", sizeof (title));
			else
				(void) strlcpy(title, tok, sizeof (title));
		} else if (strcmp(tok, "bootfs") == 0) {
			char *bootfs = strtok(NULL, " \t\r\n");
			if (bootfs == NULL)
				continue;

			if (strcmp(bootfs, be_root_ds) == 0) {
				found_be = B_TRUE;
				break;
			}
		}
	}
	(void) fclose(grub_fp);

	if (found_be) {
		/*
		 * If an entry for this BE was already in the menu, then if
		 * that entry's title matches what we would have put in
		 * return success.  Otherwise return failure.
		 */
		char *new_title = description ? description : be_name;
		if (strcmp(title, new_title) == 0) {
			return (0);
		} else {
			be_print_err(gettext("be_append_grub: "
			    "BE entry already exists in grub menu: %s\n"),
			    be_name);
			return (1);
		}
	}

	/* Append BE entry to the end of the file */
	grub_fp = fopen(grub_file, "a+");
	if (grub_fp == NULL) {
		be_print_err(gettext("be_append_grub: failed "
		    "to open menu.lst file %s\n"), grub_file);
		return (1);
	}

	(void) fprintf(grub_fp, "title %s\n",
	    description ? description : be_name);
	(void) fprintf(grub_fp, "bootfs %s\n", be_root_ds);
	(void) fprintf(grub_fp, "kernel$ /platform/i86pc/kernel/$ISADIR/unix "
	    "-B $ZFS-BOOTFS\n");
	(void) fprintf(grub_fp, "module$ "
	    "/platform/i86pc/$ISADIR/boot_archive\n");
	(void) fprintf(grub_fp, "%s\n", BE_GRUB_COMMENT);
	(void) fclose(grub_fp);

	return (0);
}

/*
 * Function:	be_remove_grub
 * Description:	Removes a BE's entry from a menu.lst file.
 * Parameters:
 *		be_name - the name of BE whose entry is to be removed from
 *			the menu.lst file.
 *		be_root_pool - the pool that be_name lives in.
 *		boot_pool -
 * Returns:
 *		0 - Success
 *		1 - Failure
 * Scope:
 *		Semi-private (library wide use only)
 */
int
be_remove_grub(char *be_name, char *be_root_pool, char *boot_pool)
{
	zfs_handle_t	*zhp = NULL;
	char		pool_mntpnt[MAXPATHLEN];
	char		be_root_ds[MAXPATHLEN];
	char		**buffer = NULL;
	char		menu_buf[BUFSIZ];
	char		menu[MAXPATHLEN];
	char		*tmp_menu = NULL;
	FILE		*menu_fp = NULL;
	FILE		*tmp_menu_fp = NULL;
	int		i;
	int		fd;
	int		nlines = 0;
	int		default_entry = 0;
	int		entry_cnt = 0;
	int		entry_del = 0;
	int		num_entry_del = 0;
	boolean_t	write = B_TRUE;
	boolean_t	do_buffer = B_FALSE;

	if (boot_pool == NULL)
		boot_pool = be_root_pool;

	/* Get name of BE's root dataset */
	be_make_root_ds(be_root_pool, be_name, be_root_ds, sizeof (be_root_ds));

	/* Get handle to pool dataset */
	if ((zhp = zfs_open(g_zfs, be_root_pool, ZFS_TYPE_DATASET)) == NULL) {
		be_print_err(gettext("be_remove_grub: "
		    "failed to open pool dataset for %s: %s"),
		    be_root_pool, libzfs_error_description(g_zfs));
		return (1);
	}

	/* Get location of where pool dataset is mounted */
	if (zfs_prop_get(zhp, ZFS_PROP_MOUNTPOINT, pool_mntpnt,
	    sizeof (pool_mntpnt), NULL, NULL, 0, B_FALSE) != 0) {
		be_print_err(gettext("be_remove_grub: "
		    "failed to get mountpoint for pool dataset %s: %s\n"),
		    zfs_get_name(zhp), libzfs_error_description(g_zfs));
		return (1);
	}
	zfs_close(zhp);

	/* Get path to GRUB menu */
	(void) strlcpy(menu, pool_mntpnt, sizeof (menu));
	(void) strlcat(menu, "/boot/grub/menu.lst", sizeof (menu));

	/* Get handle to GRUB menu file */
	if ((menu_fp = fopen(menu, "r")) == NULL) {
		be_print_err(gettext("be_remove_grub: "
		    "failed to open menu.lst (%s)\n"), menu);
		return (1);
	}

	/* Create a tmp file for the modified menu.lst */
	if ((tmp_menu = (char *)malloc(strlen(menu) + 7)) == NULL) {
		be_print_err(gettext("be_remove_grub: malloc failed\n"));
		return (1);
	}
	(void) memset(tmp_menu, 0, strlen(menu) + 7);
	(void) strcpy(tmp_menu, menu);
	(void) strcat(tmp_menu, "XXXXXX");
	if ((fd = mkstemp(tmp_menu)) == -1) {
		be_print_err(gettext("be_remove_grub: mkstemp failed\n"));
		free(tmp_menu);
		fclose(menu_fp);
		return (1);
	}
	if ((tmp_menu_fp = fdopen(fd, "w")) == NULL) {
		be_print_err(gettext("be_remove_grub: "
		    "could not open tmp file for write\n"));
		free(tmp_menu);
		fclose(menu_fp);
		return (1);
	}

	while (fgets(menu_buf, BUFSIZ, menu_fp)) {
		char tline [BUFSIZ];
		char *tok = NULL;

		strlcpy(tline, menu_buf, sizeof (tline));

		/* Tokenize line */
		tok = strtok(tline, " \t\r\n");

		if (tok == NULL || tok[0] == '#') {
			/* Found empty line or comment line */
			if (do_buffer) {
				/* Buffer this line */
				if ((buffer = (char **)realloc(buffer,
				    sizeof (char *)*(nlines + 1))) == NULL)
					return (1);
				buffer[nlines++] = strdup(menu_buf);

			} else if (write || strncmp(menu_buf, BE_GRUB_COMMENT,
			    strlen(BE_GRUB_COMMENT)) != 0) {
				/* Write this line out */
				fputs(menu_buf, tmp_menu_fp);
			}
		} else if (strcmp(tok, "default") == 0) {
			/*
			 * Record what 'default' is set to because we might
			 * need to adjust this upon deleting an entry.
			 */
			tok = strtok(NULL, " \t\r\n");

			if (tok != NULL) {
				default_entry = atoi(tok);
			}

			fputs(menu_buf, tmp_menu_fp);
		} else if (strcmp(tok, "title") == 0) {
			char *name = NULL;

			/*
			 * If we've reached a 'title' line and do_buffer is
			 * is true, that means we've just buffered an entire
			 * entry without finding a 'bootfs' directive.  We
			 * need to write that entry out and keep searching.
			 */
			if (do_buffer) {
				for (i = 0; i < nlines; i++) {
					fputs(buffer[i], tmp_menu_fp);
					free(buffer[i]);
				}
				free(buffer);
				buffer = NULL;
				nlines = 0;
			}

			/*
			 * Turn writing off and buffering on, and increment
			 * our entry counter.
			 */
			write = B_FALSE;
			do_buffer = B_TRUE;
			entry_cnt++;

			/* Buffer this 'title' line */
			if ((buffer = (char **)realloc(buffer,
			    sizeof (char *)*(nlines + 1))) == NULL)
				return (1);
			buffer[nlines++] = strdup(menu_buf);

		} else if (strcmp(tok, "bootfs") == 0) {
			char *bootfs = NULL;

			/*
			 * Found a 'bootfs' line.  See if it matches the
			 * BE we're looking for.
			 */
			if ((bootfs = strtok(NULL, " \t\r\n")) == NULL ||
			    strcmp(bootfs, be_root_ds) != 0) {
				/*
				 * Either there's nothing after the 'bootfs'
				 * or this is not the BE we're looking for,
				 * write out the line(s) we've buffered since
				 * finding the title.
				 */
				for (i = 0; i < nlines; i++) {
					fputs(buffer[i], tmp_menu_fp);
					free(buffer[i]);
				}
				free(buffer);
				buffer = NULL;
				nlines = 0;

				/*
				 * Turn writing back on, and turn off buffering
				 * since this isn't the entry we're looking
				 * for.
				 */
				write = B_TRUE;
				do_buffer = B_FALSE;

				/* Write this 'bootfs' line out. */
				fputs(menu_buf, tmp_menu_fp);
			} else {
				/*
				 * Found the entry we're looking for.
				 * Record its entry number, increment the
				 * number of entries we've deleted, and turn
				 * writing off.  Also, throw away the lines
				 * we've buffered for this entry so far, we
				 * don't need them.
				 */
				entry_del = entry_cnt - 1;
				num_entry_del++;
				write = B_FALSE;
				do_buffer = B_FALSE;

				for (i = 0; i < nlines; i++) {
					free(buffer[i]);
				}
				free(buffer);
				buffer = NULL;
				nlines = 0;
			}
		} else {
			if (do_buffer) {
				/* Buffer this line */
				if ((buffer = (char **)realloc(buffer,
				    sizeof (char *)*(nlines + 1))) == NULL)
					return (1);
				buffer[nlines++] = strdup(menu_buf);
			} else if (write) {
				/* Write this line out */
				fputs(menu_buf, tmp_menu_fp);
			}
		}
	}

	if (buffer != NULL)
		free(buffer);

	(void) fclose(menu_fp);
	(void) fclose(tmp_menu_fp);

	/* Copy the modified menu.lst into place */
	if (rename(tmp_menu, menu) != 0) {
		be_print_err(gettext("be_remove_grub: "
		    "failed to rename file %s to %s\n"),
		    tmp_menu, menu);
		free(tmp_menu);
		return (1);
	}

	free(tmp_menu);

	/*
	 * If we've removed an entry, see if we need to
	 * adjust the default value in the menu.lst.  If the
	 * entry we've deleted comes before the default entry
	 * we need to adjust the default value accordingly.
	 */
	if (num_entry_del > 0) {
		if (entry_del <= default_entry) {
			default_entry = default_entry - num_entry_del;
			if (default_entry < 0)
				default_entry = 0;

			/*
			 * Adjust the default value by rewriting the
			 * menu.lst file.  This may be overkill, but to
			 * preserve the location of the 'default' entry
			 * in the file, we need to do this.
			 */

			/* Get handle to GRUB menu file */
			if ((menu_fp = fopen(menu, "r")) == NULL) {
				be_print_err(gettext("be_remove_grub: "
				    "failed to open menu.lst (%s)\n"), menu);
				return (1);
			}

			/* Create a tmp file for the modified menu.lst */
			if ((tmp_menu = (char *)malloc(strlen(menu) + 7))
			    == NULL) {
				be_print_err(gettext("be_remove_grub: "
				    "malloc failed\n"));
				fclose(menu_fp);
				return (1);
			}
			(void) memset(tmp_menu, 0, strlen(menu) + 7);
			(void) strcpy(tmp_menu, menu);
			(void) strcat(tmp_menu, "XXXXXX");
			if ((fd = mkstemp(tmp_menu)) == -1) {
				be_print_err(gettext("be_remove_grub: "
				    "mkstemp failed\n"));
				fclose(menu_fp);
				free(tmp_menu);
				return (1);
			}
			if ((tmp_menu_fp = fdopen(fd, "w")) == NULL) {
				be_print_err(gettext("be_remove_grub: "
				    "could not open tmp file for write\n"));
				fclose(menu_fp);
				free(tmp_menu);
				return (1);
			}

			while (fgets(menu_buf, BUFSIZ, menu_fp)) {
				char tline [BUFSIZ];
				char *tok = NULL;

				strlcpy(tline, menu_buf, sizeof (tline));

				/* Tokenize line */
				tok = strtok(tline, " \t\r\n");

				if (tok == NULL) {
					/* Found empty line, write it out */
					fputs(menu_buf, tmp_menu_fp);
				} else if (strcmp(tok, "default") == 0) {
					/* Found the default line, adjust it */
					(void) snprintf(tline, sizeof (tline),
					    "default %d\n", default_entry);

					fputs(tline, tmp_menu_fp);
				} else {
					/* Pass through all other lines */
					fputs(menu_buf, tmp_menu_fp);
				}
			}

			(void) fclose(menu_fp);
			(void) fclose(tmp_menu_fp);

			/* Copy the modified menu.lst into place */
			if (rename(tmp_menu, menu) != 0) {
				be_print_err(gettext("be_remove_grub: "
				    "failed to rename file %s to %s\n"),
				    tmp_menu, menu);
				free(tmp_menu);
				return (1);
			}

			free(tmp_menu);
		}
	}

	return (0);
}

/*
 * Function:	be_default_grub_bootfs
 * Description:	This function returns the dataset in the default entry of
 *		the grub menu. If no default entry is found with a bootfs
 *		entry NULL is returned.
 * Parameters:
 *		be_root_pool - This is the name of the root pool where the
 *			       grub menu can be found.
 * Returns:
 *		Success - The default dataset is returned.
 *		Failure - NULL is returned.
 * Scope:
 *		Semi-private (library wide use only)
 */
char *
be_default_grub_bootfs(const char *be_root_pool)
{
	char		grub_file[MAXPATHLEN];
	FILE		*menu_fp;
	char		line[BUFSIZ];
	int		default_entry = 0, entries = 0, err = 0;
	int		found_default = 0;

	(void) snprintf(grub_file, MAXPATHLEN, "/%s/boot/grub/menu.lst",
	    be_root_pool);
	if ((menu_fp = fopen(grub_file, "r")) == NULL) {
		err = errno;
		be_print_err(gettext("be_default_grub_bootfs: "
		    "failed to open %s file err is %d\n"),
		    grub_file, err);
		return (NULL);
	}
	while (fgets(line, BUFSIZ, menu_fp)) {
		char *tok = strtok(line, " \t\r\n");
		if (tok != NULL && tok[0] != '#') {
			if (!found_default) {
				if (strcmp(tok, "default") == 0) {
					tok = strtok(NULL, " \t\r\n");
					if (tok != NULL) {
						default_entry = atoi(tok);
						rewind(menu_fp);
						found_default = 1;
					}
				}
				continue;
			}
			if (strcmp(tok, "title") == 0) {
				entries++;
			} else if (default_entry == entries - 1) {
				if (strcmp(tok, "bootfs") == 0) {
					tok = strtok(NULL, " \t\r\n");
					fclose(menu_fp);
					return (tok?strdup(tok):NULL);
				}
			} else if (default_entry < entries - 1) {
				/*
				 * no bootfs entry for the default entry.
				 */
				break;
			}
		}
	}
	fclose(menu_fp);
	return (NULL);
}

/*
 * Function:	be_change_grub_default
 * Description:	This function takes two parameters. These are the name of
 *		the BE we want to have as the default booted in the grub
 *		menu and the root pool where the path to the grub menu exists.
 *		The code takes this and finds the BE's entry in the grub menu
 *		and changes the default entry to point to that entry in the
 *		list.
 * Parameters:
 *		be_name - This is the name of the BE wanted as the default
 *			for the next boot.
 *		be_root_pool - This is the name of the root pool where the
 *			grub menu can be found.
 * Returns:
 *		0 - Success
 *		1 - Failure
 * Scope:
 *		Semi-private (library wide use only)
 */
int
be_change_grub_default(char *be_name, char *be_root_pool)
{
	char	grub_file[MAXPATHLEN];
	char	*temp_grub;
	char	line[BUFSIZ];
	char	temp_line[BUFSIZ];
	char	be_root_ds[MAXPATHLEN];
	FILE	*grub_fp = NULL;
	FILE	*temp_fp = NULL;
	int	fd, err = 0, entries = 0;
	boolean_t	found_default = B_FALSE;

	/* Generate string for BE's root dataset */
	be_make_root_ds(be_root_pool, be_name, be_root_ds, sizeof (be_root_ds));

	(void) snprintf(grub_file, MAXPATHLEN, "/%s/boot/grub/menu.lst",
	    be_root_pool);

	if ((grub_fp = fopen(grub_file, "r+")) == NULL) {
		err = errno;
		be_print_err(gettext("be_change_grub_default: "
		    "failed to open %s file err is %d\n"),
		    grub_file, err);
		return (1);
	}
	/* Create a tmp file for the modified menu.lst */
	if ((temp_grub = (char *)malloc(strlen(grub_file) + 7)) == NULL) {
		be_print_err(gettext("be_change_grub_default: "
		    "malloc failed\n"));
		fclose(grub_fp);
		return (1);
	}
	(void) memset(temp_grub, 0, strlen(grub_file) + 7);
	(void) strcpy(temp_grub, grub_file);
	(void) strcat(temp_grub, "XXXXXX");
	if ((fd = mkstemp(temp_grub)) == -1) {
		be_print_err(gettext("be_change_grub_default: "
		    "mkstemp failed\n"));
		fclose(grub_fp);
		free(temp_grub);
		return (1);
	}
	if ((temp_fp = fdopen(fd, "w")) == NULL) {
		err = errno;
		be_print_err(gettext("be_change_grub_default: "
		    "failed to open %s file, err is %d\n"),
		    temp_grub, err);
		close(fd);
		fclose(grub_fp);
		free(temp_grub);
		return (1);
	}

	while (fgets(line, BUFSIZ, grub_fp)) {
		char *tok = strtok(line, " \t\r\n");

		if (tok == NULL || tok[0] == '#') {
			continue;
		} else if (strcmp(tok, "title") == 0) {
			entries++;
			continue;
		} else if (strcmp(tok, "bootfs") == 0) {
			char *bootfs = strtok(NULL, " \t\r\n");
			if (bootfs == NULL)
				continue;

			if (strcmp(bootfs, be_root_ds) == 0) {
				found_default = B_TRUE;
				break;
			}
		}
	}

	if (!found_default) {
		(void) fclose(grub_fp);
		(void) fclose(temp_fp);
		be_print_err(gettext("be_change_grub_default: failed "
		    "to find entry for %s in the grub menu\n"),
		    be_name);
		return (1);
	}

	rewind(grub_fp);

	while (fgets(line, BUFSIZ, grub_fp)) {
		strncpy(temp_line, line, BUFSIZ);
		if (strcmp(strtok(temp_line, " "), "default") == 0) {
			(void) snprintf(temp_line, BUFSIZ, "default %d\n",
			    entries - 1 >= 0 ? entries - 1 : 0);
			fputs(temp_line, temp_fp);
		} else {
			fputs(line, temp_fp);
		}
	}

	(void) fclose(grub_fp);
	(void) fclose(temp_fp);

	if (rename(temp_grub, grub_file) != 0) {
		be_print_err(gettext("be_change_grub_default: "
		    "failed to rename file %s to %s\n"),
		    temp_grub, grub_file);
		err = 1;
	}
	free(temp_grub);
	return (err);
}

/*
 * Function:	be_update_grub
 * Description:	This function is used by be_rename to change the BE name in
 *		an existing entry in the grub menu to the new name of the BE.
 * Parameters:
 *		be_orig_name - the original name of the BE
 *		be_new_name - the new name the BE is being renameed to.
 *		be_root_pool - The pool which contains the grub menu
 *		boot_pool - the pool where the BE is, if different than
 *			the pool containing the grub menu.  If this is NULL
 *			it will be set to be_root_pool.
 * Returns:
 *		0 - Success
 *		> 0 - Failure
 * Scope:
 *		Semi-private (library wide use only)
 */
int
be_update_grub(char *be_orig_name, char *be_new_name, char *be_root_pool,
    char *boot_pool)
{
	zfs_handle_t *zhp = NULL;
	char grub_file[MAXPATHLEN];
	char be_root_ds[MAXPATHLEN];
	char pool_mntpnt[MAXPATHLEN];
	char be_new_root_ds[MAXPATHLEN];
	char line[BUFSIZ];
	char *temp_grub;
	FILE *menu_fp = NULL;
	FILE *new_fp = NULL;
	int tmp_fd;
	int err = 0;

	if (boot_pool == NULL)
		boot_pool = be_root_pool;

	if ((zhp = zfs_open(g_zfs, be_root_pool, ZFS_TYPE_DATASET)) == NULL) {
		be_print_err(gettext("be_update_grub: failed to open "
		    "pool dataset for %s\n"), be_root_pool);
		return (1);
	}

	(void) zfs_prop_get(zhp, ZFS_PROP_MOUNTPOINT, pool_mntpnt,
	    sizeof (pool_mntpnt), NULL, NULL, 0, B_FALSE);

	zfs_close(zhp);

	(void) snprintf(grub_file, sizeof (grub_file),
	    "%s/boot/grub/menu.lst", pool_mntpnt);

	be_make_root_ds(be_root_pool, be_orig_name, be_root_ds,
	    sizeof (be_root_ds));
	be_make_root_ds(be_root_pool, be_new_name, be_new_root_ds,
	    sizeof (be_new_root_ds));

	menu_fp = fopen(grub_file, "r");
	if (menu_fp == NULL) {
		be_print_err(gettext("be_update_grub: failed "
		    "to open menu.lst file %s\n"), grub_file);
		return (1);
	}

	/* Create tmp file for modified menu.lst */
	if ((temp_grub = (char *)malloc(strlen(grub_file) + 7))
	    == NULL) {
		be_print_err(gettext("be_update_grub: "
		    "malloc failed\n"));
		fclose(menu_fp);
		return (1);
	}
	(void) memset(temp_grub, 0, strlen(grub_file) + 7);
	(void) strcpy(temp_grub, grub_file);
	(void) strcat(temp_grub, "XXXXXX");
	if ((tmp_fd = mkstemp(temp_grub)) == -1) {
		be_print_err(gettext("be_update_grub: "
		    "mkstemp failed\n"));
		fclose(menu_fp);
		free(temp_grub);
		return (1);
	}
	if ((new_fp = fdopen(tmp_fd, "w")) == NULL) {
		be_print_err(gettext("be_update_grub: "
		    "fdopen failed\n"));
		close(tmp_fd);
		fclose(menu_fp);
		free(temp_grub);
		return (1);
	}

	while (fgets(line, BUFSIZ, menu_fp)) {
		char tline[BUFSIZ];
		char new_line[BUFSIZ];
		char *c = NULL;

		strlcpy(tline, line, sizeof (tline));

		/* Tokenize line */
		c = strtok(tline, " \t\r\n");

		if (c == NULL) {
			/* Found empty line, write it out. */
			fputs(line, new_fp);
		} else if (c[0] == '#') {
			/* Found a comment line, write it out. */
			fputs(line, new_fp);
		} else if (strcmp(c, "title") == 0) {
			char *name = NULL;
			char *desc = NULL;

			/*
			 * Found a 'title' line, parse out BE name or
			 * the description.
			 */
			name = strtok(NULL, " \t\r\n");

			if (name == NULL) {
				/*
				 * Nothing after 'title', just push
				 * this line through
				 */
				fputs(line, new_fp);
			} else {
				/*
				 * Grab the remainder of the title which
				 * could be a multi worded description
				 */
				desc = strtok(NULL, "\n");

				if (strcmp(name, be_orig_name) == 0) {
					/*
					 * The first token of the title is
					 * the old BE name, replace it with
					 * the new one, and write it out
					 * along with the remainder of
					 * description if there is one.
					 */
					if (desc) {
						(void) snprintf(new_line,
						    sizeof (new_line),
						    "title %s %s\n",
						    be_new_name, desc);
					} else {
						(void) snprintf(new_line,
						    sizeof (new_line),
						    "title %s\n", be_new_name);
					}

					fputs(new_line, new_fp);
				} else {
					fputs(line, new_fp);
				}
			}
		} else if (strcmp(c, "bootfs") == 0) {
			/*
			 * Found a 'bootfs' line, parse out the BE root
			 * dataset value.
			 */
			char *root_ds = strtok(NULL, " \t\r\n");

			if (root_ds == NULL) {
				/*
				 * Nothing after 'bootfs', just push
				 * this line through
				 */
				fputs(line, new_fp);
			} else {
				/*
				 * If this bootfs is the one we're renaming,
				 * write out the new root dataset value
				 */
				if (strcmp(root_ds, be_root_ds) == 0) {
					(void) snprintf(new_line,
					    sizeof (new_line), "bootfs %s\n",
					    be_new_root_ds);

					fputs(new_line, new_fp);
				} else {
					fputs(line, new_fp);
				}
			}
		} else {
			/*
			 * Found some other line we don't care
			 * about, write it out.
			 */
			fputs(line, new_fp);
		}
	}

	fclose(menu_fp);
	fclose(new_fp);
	close(tmp_fd);

	if (rename(temp_grub, grub_file) != 0) {
		be_print_err(gettext("be_update_grub: "
		    "failed to rename file %s to %s\n"),
		    temp_grub, grub_file);
		err = 1;
	}
	free(temp_grub);

	return (err);
}

/*
 * Function:	be_update_vfstab
 * Description:	This function digs into a BE's vfstab and updates all
 *		entries with file systems listed in be_fs_list_data_t.
 *		The entry's zpool and be_name will be updated with the
 *		zpool and be_name passed in.
 * Parameters:
 *		be_name - name of BE to update
 *		zpool - name of pool BE resides in
 *		fld - be_fs_list_data_t pointer providing the list of
 *			file systems to look for in vfstab.
 *		mountpoint - directory of where BE is currently mounted.
 *			If NULL, then BE is not currently mounted.
 * Returns:
 *		0 - Success
 *		1 - Failure
 * Scope:
 *		Semi-private (library wide use only)
 */
int
be_update_vfstab(char *be_name, char *zpool, be_fs_list_data_t *fld,
    char *mountpoint)
{
	struct vfstab	vp;
	char		*tmp_mountpoint = NULL;
	char		alt_vfstab[MAXPATHLEN];
	char		*tmp_vfstab = NULL;
	char		comments_buf[BUFSIZ];
	FILE		*comments = NULL;
	FILE		*vfs_ents = NULL;
	FILE		*tfile = NULL;
	FILE		*fp = NULL;
	struct stat	sb;
	char		dev[MAXPATHLEN];
	char		*c;
	int		fd;
	int		ret = 0;
	int		i;
	boolean_t	found_root = B_FALSE;

	if (fld == NULL || fld->fs_list == NULL || fld->fs_num == 0)
		return (0);

	/* If BE not already mounted, mount the BE */
	if (mountpoint == NULL) {
		if (_be_mount(be_name, &tmp_mountpoint, 0) != 0) {
			be_print_err(gettext("be_update_vfstab: "
			    "failed to mount BE (%s)\n"), be_name);
			return (1);
		}
	} else {
		tmp_mountpoint = mountpoint;
	}

	/* Get string for vfstab in the mounted BE. */
	(void) snprintf(alt_vfstab, sizeof (alt_vfstab), "%s/etc/vfstab",
	    tmp_mountpoint);

	/*
	 * Open vfstab for reading twice.  First is for comments,
	 * second is for actual entries.
	 */
	if ((comments = fopen(alt_vfstab, "r")) == NULL ||
	    (vfs_ents = fopen(alt_vfstab, "r")) == NULL) {
		be_print_err(gettext("be_update_vfstab: "
		    "failed to open vfstab (%s)\n"), alt_vfstab);
		ret = 1;
		goto cleanup;
	}

	/* Grab the stats of the original vfstab file */
	if (stat(alt_vfstab, &sb) != 0) {
		be_print_err(gettext("be_update_vfstab: "
		    "failed to stat file %s\n"), alt_vfstab);
		ret = 1;
		goto cleanup;
	}

	/* Create tmp file for modified vfstab */
	if ((tmp_vfstab = (char *)malloc(strlen(alt_vfstab) + 7))
	    == NULL) {
		be_print_err(gettext("be_update_vfstab: "
		    "malloc failed\n"));
		ret = 1;
		goto cleanup;
	}
	(void) memset(tmp_vfstab, 0, strlen(alt_vfstab) + 7);
	(void) strcpy(tmp_vfstab, alt_vfstab);
	(void) strcat(tmp_vfstab, "XXXXXX");
	if ((fd = mkstemp(tmp_vfstab)) == -1) {
		be_print_err(gettext("be_update_vfstab: "
		    "mkstemp failed\n"));
		ret = 1;
		goto cleanup;
	}
	if ((tfile = fdopen(fd, "w")) == NULL) {
		be_print_err(gettext("be_update_vfstab: "
		    "could not open file for write\n"));
		(void) close(fd);
		ret = 1;
		goto cleanup;
	}

	while (fgets(comments_buf, BUFSIZ, comments)) {
		for (c = comments_buf; *c != '\0' && isspace(*c); c++)
			;
		if (*c == '\0') {
			continue;
		} else if (*c == '#') {
			/*
			 * If line is a comment line, just put
			 * it through to the tmp vfstab.
			 */
			fputs(comments_buf, tfile);
		} else {
			/*
			 * Else line is a vfstab entry, grab it
			 * into a vfstab struct.
			 */
			if (getvfsent(vfs_ents, &vp) != 0) {
				be_print_err(gettext("be_update_vfstab: "
				    "getvfsent failed\n"));
				ret = 1;
				goto cleanup;
			}

			if (vp.vfs_special == NULL || vp.vfs_mountp == NULL) {
				putvfsent(tfile, &vp);
				continue;
			}

			/*
			 * TODO: As long as we're still needing to support
			 * legacy mounting of a BE root, we need to keep track
			 * of whether or not we've encountered a root entry.
			 */
			if (strcmp(vp.vfs_mountp, "/") == 0)
				found_root = B_TRUE;

			/*
			 * If the entry is one of the entries in the list
			 * of file systems to update, modify it's device
			 * field to be correct for this BE.
			 */
			for (i = 0; i < fld->fs_num; i++) {
				if (strcmp(vp.vfs_special, fld->fs_list[i])
				    == 0) {
					/*
					 * Found entry that needs an update.
					 * Replace the zpool and be_name in the
					 * entry's device.
					 */
					(void) strlcpy(dev, vp.vfs_special,
					    sizeof (dev));

					if (update_dataset(dev, sizeof (dev),
					    be_name, zpool) != 0) {
						be_print_err(
						    gettext("be_update_vfstab: "
						    "Failed to update device "
						    "field for vfstab entry "
						    "%s\n"), fld->fs_list[i]);
						ret = 1;
						goto cleanup;
					}

					vp.vfs_special = dev;
					break;
				}
			}

			/* Put entry through to tmp vfstab */
			putvfsent(tfile, &vp);
		}
	}

	(void) fclose(comments);
	comments = NULL;
	(void) fclose(vfs_ents);
	vfs_ents = NULL;
	(void) fclose(tfile);
	tfile = NULL;

	/* Copy tmp vfstab into place */
	if (rename(tmp_vfstab, alt_vfstab) != 0) {
		be_print_err(gettext("be_update_vfstab: "
		    "failed to rename file %s to %s\n"), tmp_vfstab,
		    alt_vfstab);
		ret = 1;
		goto cleanup;
	}

	/* Set the perms and ownership of the updated file */
	if (chmod(alt_vfstab, sb.st_mode) != 0) {
		be_print_err(gettext("be_update_vfstab: "
		    "failed to chmod %s\n"), alt_vfstab);
		ret = 1;
		goto cleanup;
	}
	if (chown(alt_vfstab, sb.st_uid, sb.st_gid) != 0) {
		be_print_err(gettext("be_update_vfstab: "
		    "failed to chown %s\n"), alt_vfstab);
		ret = 1;
		goto cleanup;
	}

	/*
	 * TODO: As long as we're still needing to support legacy mounting
	 * of a BE root, we need to make sure the vfstab has a root entry.
	 * If it didn't, add one.
	 */
	if (!found_root) {
		/* No root entry in vfstab, add it */
		if ((fp = fopen(alt_vfstab, "a+")) == NULL) {
			be_print_err(gettext("be_update_vfstab: "
			    "failed to open vfstab (%s)\n"), alt_vfstab);
			ret = 1;
			goto cleanup;
		}

		be_make_root_ds(zpool, be_name, dev, sizeof (dev));

		vp.vfs_special = dev;
		vp.vfs_fsckdev = "-";
		vp.vfs_mountp = "/";
		vp.vfs_fstype = "zfs";
		vp.vfs_fsckpass = "-";
		vp.vfs_automnt = "no";
		vp.vfs_mntopts = "-";

		putvfsent(fp, &vp);
		(void) fclose(fp);
	}

cleanup:
	if (comments != NULL)
		(void) fclose(comments);
	if (vfs_ents != NULL)
		(void) fclose(vfs_ents);
	(void) unlink(tmp_vfstab);
	if (tmp_vfstab != NULL)
		(void) free(tmp_vfstab);
	if (tfile != NULL)
		(void) fclose(tfile);

	/* Unmount BE if we mounted it */
	if (mountpoint == NULL) {
		if (_be_unmount(be_name, 0) == 0) {
			/* Remove temporary mountpoint */
			rmdir(tmp_mountpoint);
		} else {
			be_print_err(gettext("be_update_vfstab: "
			    "failed to unmount BE %s mounted at %s\n"),
			    be_name, tmp_mountpoint);
			ret = 1;
		}

		free(tmp_mountpoint);
	}

	return (ret);
}

/*
 * Function:	be_auto_snap_name
 * Description:	Generate an auto snapshot name constructed based on the
 *		BE policy passed in and the current date and time.  The
 *		auto snapshot name is of the form:
 *
 *			<policy>:<reserved>:<date>-<time>
 *
 *		The <reserved> component is currently not being used and
 *		is left as the string, "-".
 * Parameters:
 *		policy - name of policy to generate this auto snapshot name
 *			with.
 * Returns:
 *		Success - pointer to auto generated snapshot name.  The name
 *			is allocated in heap storage so the caller is
 *			responsible for free'ing the name.
 *		Failure - NULL
 * Scope:
 *		Semi-private (library wide use only)
 */
char *
be_auto_snap_name(char *policy)
{
	time_t		utc_tm = NULL;
	struct tm	*gmt_tm = NULL;
	char		*reserved = "-"; /* Currently not supported */
	char		gmt_time_str[64];
	char		auto_snap_name[ZFS_MAXNAMELEN];

	if (time(&utc_tm) == -1) {
		be_print_err(gettext("be_auto_snap_name: time() failed\n"));
		return (NULL);
	}

	if ((gmt_tm = gmtime(&utc_tm)) == NULL) {
		be_print_err(gettext("be_auto_snap_name: gmtime() failed\n"));
		return (NULL);
	}

	strftime(gmt_time_str, sizeof (gmt_time_str), "%F-%T", gmt_tm);

	(void) snprintf(auto_snap_name, sizeof (auto_snap_name), "%s:%s:%s",
	    policy, reserved, gmt_time_str);

	return (strdup(auto_snap_name));
}

/*
 * Function:	be_auto_be_name
 * Description:	Generate an auto BE name constructed based on the BE name
 *		of the original BE being cloned.
 * Parameters:
 *		obe_name - name of the original BE being cloned.
 * Returns:
 *		Success - pointer to auto generated BE name.  The name
 *			is allocated in heap storage so the caller is
 *			responsible for free'ing the name.
 *		Failure - NULL
 * Scope:
 *		Semi-private (library wide use only)
 */
char *
be_auto_be_name(char *obe_name)
{
	be_node_list_t	*be_nodes = NULL;
	be_node_list_t	*cur_be = NULL;
	char		auto_be_name[MAXPATHLEN];
	char		base_be_name[MAXPATHLEN];
	char		cur_be_name[MAXPATHLEN];
	char		*num_str = NULL;
	char		*c = NULL;
	int		num = 0;
	int		prev_cur_num, cur_num = 0;

	/*
	 * Check if obe_name is already in an auto BE name format.
	 * If it is, then strip off the increment number to get the
	 * base name.
	 */
	(void) strlcpy(base_be_name, obe_name, sizeof (base_be_name));

	if ((num_str = strrchr(base_be_name, BE_AUTO_NAME_DELIM))
	    != NULL) {
		/* Make sure remaining string is all digits */
		c = num_str + 1;
		while (c[0] != '\0' && isdigit(c[0]))
			c++;
		/*
		 * If we're now at the end of the string strip off the
		 * increment number.
		 */
		if (c[0] == '\0')
			num_str[0] = '\0';
	}

	if (_be_list(NULL, &be_nodes) != 0) {
		be_print_err(gettext("be_auto_be_name: be_list failed\n"));
		return (NULL);
	}

	for (cur_be = be_nodes; cur_be != NULL; cur_be = cur_be->be_next_node) {
		(void) strlcpy(cur_be_name, cur_be->be_node_name,
		    sizeof (cur_be_name));

		/* If cur_be_name doesn't match at least base be name, skip. */
		if (strncmp(cur_be_name, base_be_name, strlen(base_be_name))
		    != 0)
			continue;

		/* Get the string following the base be name */
		num_str = cur_be_name + strlen(base_be_name);

		/*
		 * If nothing follows the base be name, this cur_be_name
		 * is the BE named with the base be name, skip.
		 */
		if (num_str == NULL || num_str[0] == '\0')
			continue;

		/*
		 * Remove the name delimiter.  If its not there,
		 * cur_be_name isn't part of this BE name stream, skip.
		 */
		if (num_str[0] == BE_AUTO_NAME_DELIM)
			num_str++;
		else
			continue;

		/* Make sure remaining string is all digits */
		c = num_str;
		while (c[0] != '\0' && isdigit(c[0]))
			c++;
		if (c[0] != '\0')
			continue;

		/* Convert the number string to an int */
		cur_num = atoi(num_str);

		/*
		 * If failed to convert the string, skip it.  If its too
		 * long to be converted to an int, we wouldn't auto generate
		 * this number anyway so there couldn't be a conflict.
		 * We treat it as a manually created BE name.
		 */
		if (cur_num == 0 && errno == EINVAL)
			continue;

		/*
		 * Compare current number to current max number,
		 * take higher of the two.
		 */
		if (cur_num > num)
			num = cur_num;
	}

	/*
	 * Store off a copy of 'num' incase we need it later.  If incrementing
	 * 'num' causes it to roll over, this means 'num' is the largest
	 * positive int possible; we'll need it later in the loop to determine
	 * if we've exhausted all possible increment numbers.  We store it in
	 * 'cur_num'.
	 */
	cur_num = num;

	/* Increment 'num' to get new auto BE name number */
	if (++num <= 0) {
		int ret = 0;

		/*
		 * Since incrementing 'num' caused it to rollover, start
		 * over at 0 and find the first available number.
		 */
		for (num = 0; num < cur_num; num++) {

			snprintf(cur_be_name, sizeof (cur_be_name),
			    "%s%c%d", base_be_name, BE_AUTO_NAME_DELIM, num);

			ret = zpool_iter(g_zfs, be_exists_callback,
			    cur_be_name);

			if (ret == 0) {
				/*
				 * BE name doesn't exist, break out
				 * to use 'num'.
				 */
				break;
			} else if (ret == 1) {
				/* BE name exists, continue looking */
				continue;
			} else {
				be_print_err(gettext("be_auto_be_name: "
				    "zpool_iter failed: %s\n"),
				    libzfs_error_description(g_zfs));
				be_free_list(be_nodes);
				return (NULL);
			}
		}

		/*
		 * If 'num' equals 'cur_num', we've exhausted all possible
		 * auto BE names for this base BE name.
		 */
		if (num == cur_num) {
			be_print_err(gettext("be_auto_be_name: "
			    "No more available auto BE names for base "
			    "BE name %s\n"), base_be_name);
			be_free_list(be_nodes);
			return (NULL);
		}
	}

	be_free_list(be_nodes);

	/*
	 * Generate string for auto BE name.
	 */
	(void) snprintf(auto_be_name, sizeof (auto_be_name), "%s%c%d",
	    base_be_name, BE_AUTO_NAME_DELIM, num);

	return (strdup(auto_be_name));
}

/*
 * Function:	be_valid_be_name
 * Description:	Validates a BE name.
 * Parameters:
 *		be_name - name of BE to validate
 * Returns:
 *		B_TRUE - be_name is valid
 *		B_FALSE - be_name is invalid
 * Scope:
 *		Semi-private (library wide use only)
 */

boolean_t
be_valid_be_name(char *be_name)
{
	if (be_name == NULL)
		return (B_FALSE);

	/* A BE name must not be a multi-level dataset name */
	if (strchr(be_name, '/') != NULL)
		return (B_FALSE);

	/* The BE name must simply comply with a zfs dataset component name */
	if (!zfs_name_valid(be_name, ZFS_TYPE_FILESYSTEM))
		return (B_FALSE);

	return (B_TRUE);
}

/*
 * Function:	be_valid_auto_snap_name
 * Description:	This function checks to make sure that the auto generated name
 *		is in a valid format and that the date string is valid.
 *		Examples of valid auto snapshot names are:
 *
 *			static:-:2008-03-31-18:41:30
 *			static:-:2008-03-31-22:17:24
 *			volatile:-:2008:04-05-09:12:55
 *			volatile:-:2008:04-06-15:34:12
 *
 * Parameters:
 *		name - This is the name of the snapshot to be validated.
 * Returns:
 *		B_TRUE - the name is a valid auto snapshot name.
 *		B_FALSE - the name is not a valid auto snapshot name.
 * Scope:
 *		Semi-private (library wide use only)
 */
boolean_t
be_valid_auto_snap_name(char *name)
{
	struct tm gmt_tm;
	time_t utc_tm;

	char *policy = strdup(name);
	char *reserved;
	char *date;
	char *c;

	/*
	 * Get the first field from the snapshot name,
	 * which is the BE policy
	 */
	c = strchr(policy, ':');
	if (c == NULL) {
		free(policy);
		return (B_FALSE);
	}
	c[0] = '\0';

	/* Validate the policy name */
	if (!valid_be_policy(policy)) {
		free(policy);
		return (B_FALSE);
	}

	/* Get the next field, which is the reserved field. */
	if (c[1] == NULL || c[1] == '\0') {
		free(policy);
		return (B_FALSE);
	}
	reserved = c+1;
	c = strchr(reserved, ':');
	if (c == NULL) {
		free(policy);
		return (B_FALSE);
	}
	c[0] = '\0';

	/* Validate the reserved field */
	if (strcmp(reserved, "-") != 0) {
		free(policy);
		return (B_FALSE);
	}

	/* The remaining string should be the date field */
	if (c[1] == NULL || c[1] == '\0') {
		free(policy);
		return (B_FALSE);
	}
	date = c+1;

	/* Validate the date string by converting it into utc time */
	if (strptime(date, "%Y-%m-%d-%T", &gmt_tm) == NULL ||
	    (utc_tm = mktime(&gmt_tm)) == -1) {
		be_print_err(gettext("be_valid_auto_snap_name: "
		    "invalid auto snapshot name\n"));
		free(policy);
		return (B_FALSE);
	}

	free(policy);
	return (B_TRUE);
}

/*
 * Function:	be_default_policy
 * Description:	Temporary hardcoded policy support.  This function returns
 *		the default policy type to be used to create a BE or a BE
 *		snapshot.
 * Parameters:
 *		None
 * Returns:
 *		Name of default BE policy.
 * Scope:
 *		Semi-private (library wide use only)
 */
char *
be_default_policy(void)
{
	return (BE_PLCY_STATIC);
}

/*
 * Function:	valid_be_policy
 * Description:	Temporary hardcoded policy support.  This function valids
 *		whether a policy is a valid known policy or not.
 * Paramters:
 *		policy - name of policy to validate.
 * Returns:
 *		B_TRUE - policy is a valid.
 *		B_FALSE - policy is invalid.
 * Scope:
 *		Semi-private (library wide use only)
 */
boolean_t
valid_be_policy(char *policy)
{
	if (policy == NULL)
		return (B_FALSE);

	if (strcmp(policy, BE_PLCY_STATIC) == 0 ||
	    strcmp(policy, BE_PLCY_VOLATILE) == 0) {
		return (B_TRUE);
	}

	return (B_FALSE);
}

/*
 * Function:	be_print_err
 * Description:	This function prints out error messages if do_print is
 *		set to B_TRUE.
 * Paramters:
 *		prnt_str - the string we wish to print and any arguments
 *		for the format of that string.
 * Returns:
 *		void
 * Scope:
 *		Semi-private (library wide use only)
 */
void
be_print_err(char *prnt_str, ...)
{
	va_list ap;
	char buf[BUFSIZ];
	va_start(ap, prnt_str);
	if (do_print) {
		(void) vsprintf(buf, prnt_str, ap);
		(void) fprintf(stderr, buf);
	}
}

/* ********************************************************************	*/
/*			Private Functions				*/
/* ******************************************************************** */

/*
 * Function:	update_dataset
 * Description:	This function takes a dataset name and replaces the zpool
 *		and be_name components of the dataset with the new be_name
 *		zpool passed in.
 * Parameters:
 *		dataset - name of dataset
 *		dataset_len - lenth of buffer in which dataset is passed in.
 *		be_name - name of new BE name to update to.
 *		zpool - name of new zpool to update to.
 * Returns:
 *		0 - Success
 *		1 - Failure
 * Scope:
 *		Private
 */
static int
update_dataset(char *dataset, int dataset_len, char *be_name, char *zpool)
{
	char	*ds = NULL;
	char	*sub_ds = NULL;

	/* Tear off the BE container dataset */
	if ((ds = be_make_name_from_ds(dataset)) == NULL) {
		return (1);
	}

	/* Get dataset name relative to BE root, if there is one */
	sub_ds = strchr(ds, '/');

	/* Generate the BE root dataset name */
	be_make_root_ds(zpool, be_name, dataset, dataset_len);

	/* If a subordinate dataset name was found, append it */
	if (sub_ds != NULL)
		(void) strlcat(dataset, sub_ds, dataset_len);

	free(ds);
	return (0);
}
