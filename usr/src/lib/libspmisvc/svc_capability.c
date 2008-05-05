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
 * Functions relating to the reading and manipulating of hardware capability
 * data gathered from hardware capability scripts.
 */

#include <stdio.h>
#include <dirent.h>
#include <limits.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include "spmisvc_lib.h"
#include "spmicommon_api.h"

/* The maximum length of a key/value pair returned by one of the tests */
#define	CAPABILITY_LEN	512

static char		*capability_dir = HW_CAP_TESTS_DIRECTORY;
static StringList	*hardware_capabilities = NULL;
static StringList	*software_capabilities = NULL;

/*
 * Name:	set_capability_dir
 * Description:	Override the default capability directory with a user-supplied
 *		one.  This is to be used for debugging and in cases such as
 *		Live Upgrade where the capability tests aren't going to be
 *		accessible in the default directory.
 * Scope:	public
 * Arguments:	newdir	- [RO, *RO] (char *)
 *			  The new capability directory
 * Returns:	none
 */
void
set_hw_capability_dir(char *newdir)
{
	capability_dir = xstrdup(newdir);
}

/*
 * Name:	set_sw_capabilities
 * Description:	Set the software capabilities to be later retrieved
 *		with get_sw_capabilities.
 * Scope:	public
 * Arguments:	caps - The null-terminated array of
 *		name=value pairs representing
 *		the capabilities.  If existing capabilities are found,
 *		then the new capabilities are added to the list.
 *
 * Returns:	0		- Capabilities read successfully
 *		ERR_BADENTRY	- A bad entry was supplied
 */
int
set_sw_capabilities(char *caps[])
{
	StringList	*sw_caps;
	int		i;
	if (caps == NULL) {
	    return (ERR_BADENTRY);
	}

	for (i = 0; caps[i] != NULL; i++) {

		if (!strchr(caps[i], '=')) {
			return (ERR_BADENTRY);
		}

		StringListAdd(&software_capabilities, caps[i]);
	}

	return (0);
}

/*
 * Name:	read_hw_capabilities
 * Description:	Run the hardware capability test scripts, looking for the first
 *		one that can provide information about this system.  Save the
 *		key/value pairs returned by that script.
 * Scope:	public
 * Arguments:	none
 * Returns:	0		- Capabilities read successfully
 *		ERR_NODIR	- The capability test directory does not exist
 *		ERR_BADENTRY	- A capability test returned a bad entry
 */
int
read_hw_capabilities(void)
{
	char		testpath[PATH_MAX + 1];
	char		testcmd[PATH_MAX + 12 + 1]; /* " 2>/dev/null" */
	char		pairbuf[CAPABILITY_LEN + 2];
	StringList	*hw_caps;
	struct dirent	*dp;
	struct stat	sb;
	DIR		*dirp;
	FILE		*test;
	int		exitcode;

	/* does the directory exist? */
	if (stat(capability_dir, &sb) || !S_ISDIR(sb.st_mode)) {
		return (ERR_NODIR);
	}

	if (!(dirp = opendir(capability_dir))) {
		return (ERR_NODIR);
	}

	/* for each executable thing in the directory */
	while ((dp = readdir(dirp)) != NULL) {
		if (streq(dp->d_name, ".") || streq(dp->d_name, "..")) {
			continue;
		}

		(void) sprintf(testpath, "%s/%s", capability_dir, dp->d_name);
		if (access(testpath, X_OK) != 0) {
			continue;
		}

		/* run it */
		sprintf(testcmd, "%s 2>/dev/null", testpath);
		if (!(test = popen(testcmd, "r"))) {
			continue;
		}

		/*
		 * if it starts to emit output, stuff the
		 * data it returns into a capability list.
		 */
		hw_caps = NULL;
		while (fgets(pairbuf, CAPABILITY_LEN + 2, test)) {
			pairbuf[CAPABILITY_LEN] = '\0';

			if (pairbuf[strlen(pairbuf) - 1] == '\n') {
				pairbuf[strlen(pairbuf) - 1] = '\0';
			}

			if (!strchr(pairbuf, '=')) {
				StringListFree(hw_caps);
				hw_caps = NULL;
				return (ERR_BADENTRY);
			}

			StringListAdd(&hw_caps, pairbuf);
		}

		exitcode = pclose(test);
		if (exitcode == 0) {
			/* We matched this machine */
			hardware_capabilities = hw_caps;
			break;
		} else {
			/*
			 * We didn't match this machine.  In theory, we
			 * shouldn't have gotten any output, but free it
			 * just in case
			 */
			StringListFree(hw_caps);
			hw_caps = NULL;
		}
	}

	closedir(dirp);

	return (0);
}

/*
 * Name:	get_hw_capability
 * Description:	Get the value for a particular capability key.  This searches
 *		through the capability pairs created by read_hw_capabilities().
 *		If the given key is not found, NULL is returned.
 * Scope:	public
 * Arguments:	capname	- [RO, *RO] (char *)
 *			  The capability name to be retrieved
 * Returns:	char *	- The value of the requested capability, or NULL if
 *			  not found
 */
char *
get_hw_capability(char *capname)
{
	StringList	*capptr;

	WALK_LIST(capptr, hardware_capabilities) {
		if (ci_begins_with(capptr->string_ptr, capname) &&
		    capptr->string_ptr[strlen(capname)] == '=') {
			/* Found the capability - return the value */
			return (capptr->string_ptr + strlen(capname) + 1);
		}
	}

	/* Not found */
	return (NULL);
}

/*
 * Name:	get_sw_capability
 * Description:	Get the value for a particular capability key.  This searches
 *		through the capability pairs created by set_sw_capabilities().
 *		If the given key is not found, NULL is returned.
 * Scope:	public
 * Arguments:	capname	- [RO, *RO] (char *)
 *			  The capability name to be retrieved
 * Returns:	char *	- The value of the requested capability, or NULL if
 *			  not found
 */
char *
get_sw_capability(char *capname)
{
	StringList	*capptr;

	WALK_LIST(capptr, software_capabilities) {
		if (ci_begins_with(capptr->string_ptr, capname) &&
		    capptr->string_ptr[strlen(capname)] == '=') {
			/* Found the capability - return the value */
			return (capptr->string_ptr + strlen(capname) + 1);
		}
	}

	/* Not found */
	return (NULL);
}

#ifdef MODULE_TEST

/*
 * This test will read the capabilities from a user-specified directory, and
 * will dump the capabilities read.
 */
void
main(int argc, char **argv)
{
	StringList	*strptr;
	int		rc;

	if (argc != 2) {
		fprintf(stderr, "Usage: %s cap_dir\n", argv[0]);
		exit(set_hw_capability_dir(argv[1]);

	if ((rc = read_hw_capabilities()) != 0) {
		fprintf(stderr, "Error: read_capabilities returned %d\n", rc);
		exit(1);
	}

	printf("HW Capabilities dump:\n");
	WALK_LIST(strptr, hardware_capabilities) {
		printf("\t%s\n", strptr->string_ptr);
	}
}

#endif
