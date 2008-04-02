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

#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include <wait.h>
#include <sys/param.h>

#include <ti_bem.h>
#include <ti_api.h>
#include <ls_api.h>
#include <libbe.h>


/* global variables */

/* local constants */

/* private variables */

/* if set to B_TRUE, dry run mode is invoked, no changes done to the target */
static boolean_t	ibem_dryrun_mode_fl = B_FALSE;


/* ------------------------ private functions --------------------------- */

/*
 * ibem_debug_print()
 */
static void
ibem_debug_print(ls_dbglvl_t dbg_lvl, const char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1];

	va_start(ap, fmt);
	(void) vsprintf(buf, fmt, ap);
	(void) ls_write_dbg_message("TIBEM", dbg_lvl, buf);
	va_end(ap);
}

/*
 * Function:	ibem_system()
 *
 * Description:	Execute shell commands in a thread-safe manner
 *
 * Scope:	private
 * Parameters:	cmd - the command to execute
 *
 * Return:	if popen() fails, -1, otherwise return code from command
 *
 */

static int
ibem_system(char *cmd)
{
	FILE	*p;
	int	ret;
	char	errbuf[IBEM_MAXCMDLEN];

	/*
	 * catch stderr for debugging purposes
	 */

	if (strlcat(cmd, " 2>&1 1>/dev/null", IBEM_MAXCMDLEN) >= IBEM_MAXCMDLEN)
		ibem_debug_print(LS_DBGLVL_WARN,
		    "ibem_system: Couldn't redirect stderr\n");

	ibem_debug_print(LS_DBGLVL_INFO, "bem cmd: %s\n", cmd);

	if (!ibem_dryrun_mode_fl) {
		if ((p = popen(cmd, "r")) == NULL)
			return (-1);

		while (fgets(errbuf, sizeof (errbuf), p) != NULL)
			ibem_debug_print(LS_DBGLVL_WARN, " stderr:%s", errbuf);

		ret = pclose(p);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0))
			return (-1);
	}

	return (0);
}


/* ----------------------- public functions --------------------------- */

/*
 * Function:	ibem_create_be
 * Description:	Creates boot environment
 *
 * Scope:	public
 * Parameters:	attrs - set of attributes describing the target
 *
 * Return:	IBEM_E_SUCCESS - BE created successfully
 *		IBEM_E_ATTR_INVALID - invalid set of attributes passed
 *		IBEM_E_RPOOL_NOT_EXIST - root pool doesn't exist
 *		IBEM_E_BE_CREATE_FAILED - be_init() failed
 */

ibem_errno_t
ibem_create_be(nvlist_t *attrs)
{
	char		*be_name;
	char		*rpool_name;
	char		**fs_names, **fs_shared_names;
	uint_t		fs_num, fs_shared_num;
	char		cmd[IBEM_MAXCMDLEN];
	int		i, ret;
	nvlist_t	*be_attrs;

	assert(attrs != NULL);

	/* check, if required attributes provided */

	if (nvlist_lookup_string(attrs, TI_ATTR_BE_NAME, &be_name)
	    != 0) {
		ibem_debug_print(LS_DBGLVL_ERR, "Can't create BE, "
		    "TI_ATTR_BE_NAME is required but not defined\n");

		return (IBEM_E_ATTR_INVALID);
	}

	if (nvlist_lookup_string(attrs, TI_ATTR_BE_RPOOL_NAME, &rpool_name)
	    != 0) {
		ibem_debug_print(LS_DBGLVL_ERR, "Can't create BE, "
		    "TI_ATTR_BE_RPOOL_NAME is required but not defined\n");

		return (IBEM_E_ATTR_INVALID);
	}

	if (nvlist_lookup_string_array(attrs, TI_ATTR_BE_FS_NAMES, &fs_names,
	    &fs_num) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR, "Can't create BE, "
		    "TI_ATTR_BE_FS_NAMES is required but not defined\n");

		return (IBEM_E_ATTR_INVALID);
	}

	ibem_debug_print(LS_DBGLVL_INFO,
	    "%d filesystems will be created\n", fs_num);

	for (i = 0; i < fs_num; i++)
		ibem_debug_print(LS_DBGLVL_INFO,
		    " %s\n", fs_names[i]);

	if (nvlist_lookup_string_array(attrs, TI_ATTR_BE_SHARED_FS_NAMES,
	    &fs_shared_names, &fs_shared_num) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR, "Can't create BE, "
		    "TI_ATTR_BE_FS_NAMES is required but not defined\n");

		return (IBEM_E_ATTR_INVALID);
	} else {
		ibem_debug_print(LS_DBGLVL_INFO,
		    "%d shared filesystems will be created\n", fs_shared_num);

		for (i = 0; i < fs_shared_num; i++)
			ibem_debug_print(LS_DBGLVL_INFO,
			    " %s\n", fs_shared_names[i]);
	}

	/*
	 * Complain if root pool does not exist.
	 */

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/zpool list %s", rpool_name);

	if (ibem_system(cmd) == -1) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "root pool <%s> doesn't exist\n", rpool_name);

		return (IBEM_E_RPOOL_NOT_EXIST);
	}

	/*
	 * Convert TI attributes to BE attributes
	 */

	if (nvlist_alloc(&be_attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't create nvlist describing BE\n");

		return (IBEM_E_ATTR_INVALID);
	}

	/* add BE name */

	if (nvlist_add_string(be_attrs, BE_ATTR_NEW_BE_NAME,
	    be_name) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add BE_ATTR_NEW_BE_NAME attribute\n");

		return (IBEM_E_ATTR_INVALID);
	}

	/* add ZFS pool name */

	if (nvlist_add_string(be_attrs, BE_ATTR_NEW_BE_POOL,
	    rpool_name) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add BE_ATTR_NEW_BE_POOL attribute\n");

		return (IBEM_E_ATTR_INVALID);
	}

	/* add non-shared filesystems */

	if (nvlist_add_uint16(be_attrs, BE_ATTR_FS_NUM, fs_num) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add BE_ATTR_BE_FS_NUM attribute\n");

		return (IBEM_E_ATTR_INVALID);
	}

	if (nvlist_add_string_array(be_attrs, BE_ATTR_FS_NAMES, fs_names,
	    fs_num) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add BE_ATTR_BE_FS_NAMES attribute\n");

		return (IBEM_E_ATTR_INVALID);
	}

	/* add shared filesystems */

	if (nvlist_add_uint16(be_attrs, BE_ATTR_SHARED_FS_NUM, fs_shared_num)
	    != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add BE_ATTR_BE_FS_NUM attribute\n");

		return (IBEM_E_ATTR_INVALID);
	}

	if (nvlist_add_string_array(be_attrs, BE_ATTR_SHARED_FS_NAMES,
	    fs_shared_names, fs_shared_num) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add BE_ATTR_BE_FS_NAMES attribute\n");

		return (IBEM_E_ATTR_INVALID);
	}

	/*
	 * call BE interface for doing real job
	 */
	ret = be_init(be_attrs);

	/* release nvlist containing BE attributes */

	nvlist_free(be_attrs);

	if (ret != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "be_init() failed with error code %d\n", ret);

		return (IBEM_E_BE_CREATE_FAILED);
	}

	/* mount BE w/o shared filesystems */

	if (nvlist_alloc(&be_attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't create nvlist for mounting BE\n");

		return (IBEM_E_ATTR_INVALID);
	}

	/* add BE name */

	if (nvlist_add_string(be_attrs, BE_ATTR_ORIG_BE_NAME,
	    be_name) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add BE_ATTR_ORIG_BE_NAME attribute\n");

		return (IBEM_E_ATTR_INVALID);
	}

	/* add BE mounpoint */

	if (nvlist_add_string(be_attrs, BE_ATTR_MOUNTPOINT,
	    BE_MOUNTPOINT) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add BE_ATTR_MOUNTPOINT attribute\n");

		return (IBEM_E_ATTR_INVALID);
	}

	/* add mount flags */

	if (nvlist_add_uint16(be_attrs, BE_ATTR_MOUNT_FLAGS, 0) != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "Couldn't set zfs shared fs mount flags\n");

		return (IBEM_E_ATTR_INVALID);
	}

	ret = be_mount(be_attrs);
	nvlist_free(be_attrs);

	if (ret != 0) {
		ibem_debug_print(LS_DBGLVL_ERR,
		    "be_mount() failed with error code %d\n", ret);

		return (IBEM_E_BE_MOUNT_FAILED);
	}

	/*
	 * mount shared filesystems on alternate root
	 */

	for (i = 0; i < fs_shared_num; i++) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/zfs set mountpoint=" BE_MOUNTPOINT "%s %s%s",
		    fs_shared_names[i], rpool_name, fs_shared_names[i]);

		if (ibem_system(cmd) == -1)
			return (IBEM_E_BE_MOUNT_FAILED);

		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/zfs mount %s%s",
		    rpool_name, fs_shared_names[i]);

		if (ibem_system(cmd) == -1)
			return (IBEM_E_BE_MOUNT_FAILED);
	}

	return (IBEM_E_SUCCESS);
}

/*
 * Function:	ibem_dryrun_mode
 * Description:	Makes TI BE module work in dry run mode.
 *		No changes done to the target.
 *
 * Scope:	public
 * Parameters:
 *
 * Return:
 */

void
ibem_dryrun_mode(void)
{
	ibem_dryrun_mode_fl = B_TRUE;
}
