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
 * Snap BE discovery for Target Discovery module
 */
#include <unistd.h>
#include <libnvpair.h>
#include <strings.h>
#include <td_lib.h>
#include <td_api.h>
#include <ls_api.h>
#include "libbe.h"

/*
 * Eventual retrieval of release information pending on establishment of
 * INST_RELEASE
 */
#define INST_RELEASE_PENDING /* INST_RELEASE not yet available */

#define	TEMPLATEBE "/tmp/td_be_XXXXXX"	/* temp directory for BE mountpoints */

#define	TDMOD "TDMG"	/* module to display in log messages */

static void import_any_zpools(void);
static nvlist_t *mkbe(const char *, const char *);
static boolean_t get_rpool_devname(char *, char *, int);

/*
 * build BE attribute list
 * name - BE name
 * mp - mount point for BE
 * returns attribute list or NULL
 */
static nvlist_t *
mkbe(const char *name, const char *mp)
{
	nvlist_t *nvl;

	if (nvlist_alloc(&nvl, NV_UNIQUE_NAME, 0) != 0) {
		ls_write_log_message(TDMOD, "nvlist_alloc() failed\n");
		return (NULL);
	}
	if (nvlist_add_string(nvl, BE_ATTR_ORIG_BE_NAME, name) != 0) {
		ls_write_log_message(TDMOD, "nvlist_add_string() failed\n");
		return (NULL);
	}
	if (nvlist_add_string(nvl, BE_ATTR_MOUNTPOINT, mp) != 0) {
		ls_write_log_message(TDMOD, "nvlist_add_string() failed\n");
		return (NULL);
	}
	return (nvl);
}

/*
 * given pool name, return /dev/dsk device name to buffer
 * rpool - name of root pool
 * devname - buffer for device name
 * devnamesize - maximum size of buffer
 * returns B_TRUE if successful, B_FALSE otherwise
 */
static boolean_t
get_rpool_devname(char *rpool, char *devname, int devnamesize)
{
	char cmd[MAXPATHLEN] = "/usr/sbin/zpool status ";
	FILE *pipfp;
	char rpobuf[MAXPATHLEN]; /* popen() output buffer */

	(void) strlcat(cmd, rpool, sizeof (cmd));
	ls_write_dbg_message(TDMOD, LS_DBGLVL_INFO, "executing %s\n",cmd);
	if ((pipfp = popen(cmd, "r")) == NULL)
		return (NULL);
	/*
	 * parse zpool status command
	 * look for "config:" label
	 * skip first output line containing pool name
	 * take first token of line following it as device name
	 */
	while (fgets(rpobuf, sizeof (rpobuf), pipfp) != NULL) {
		char label[132];
		int nsc;

		nsc = sscanf(rpobuf, "%s", label);
		if (nsc == 0)
			continue;
		if (strcmp(label, "config:") == 0) {
			while (fgets(rpobuf, sizeof (rpobuf), pipfp) != NULL) {
				nsc = sscanf(rpobuf, "%s", label);
				if (nsc < 1)
					continue;
				if (strcmp(label, "NAME") == 0)
					continue;
				if (strcmp(label, rpool) == 0) {
					if (fgets(rpobuf, sizeof (rpobuf),
					    pipfp) == NULL)
						break;
					nsc = sscanf(rpobuf, "%s", label);
					if (nsc < 1)
						continue;
					(void) snprintf(devname, devnamesize,
					    "/dev/dsk/%s", label);
					ls_write_dbg_message(TDMOD,
					    LS_DBGLVL_INFO,
					    "found device %s\n", devname);
					(void) pclose(pipfp);
					return (B_TRUE);
				}
			}
		}
	}
	(void) pclose(pipfp);
	ls_write_dbg_message(TDMOD, LS_DBGLVL_INFO,
	    "finishing get_rpool_devname\n");
	return (B_FALSE);
}

/*
 * import any root pools with zpool import
 *
 * read from list of root pools not imported,
 * import them one-by-one insuring unique name
 *
 * BUG:"zpool import -f -R /mnt/zpools -a" has problems if root pools have 
 * conflicting names
 */
static void
import_any_zpools() {
	FILE *pipe_fp;
	char rpobuf[MAXPATHLEN]; /* popen() output buffer */
	char pool[132] = "", id[132] = "";
	int npools = 0;

	/* launch zpool import and parse results */
	if ((pipe_fp = popen("/usr/sbin/zpool import", "r")) == NULL)
		return;
	while (fgets(rpobuf, sizeof (rpobuf), pipe_fp) != NULL) {
		char label[132], val[132];
		int nsc;

		nsc = sscanf(rpobuf, "%s %s", label, val);
		if (nsc != 2)
			continue;
		if (strcmp(label, "pool:") == 0) {
			strlcpy(pool, val, sizeof(pool));
			continue;
		}
		if (strcmp(label, "id:") == 0) {
			strlcpy(id, val, sizeof(id));
			continue;
		}
		if (strcmp(label, "state:") == 0) {
			char buf[512];

			if (strcmp(val, "ONLINE") != 0)
				continue;
			(void) snprintf(buf, sizeof (buf),
			    "/usr/sbin/zpool "
			    "import -f -R /tmp/import_pools/p%s %s p%s",
			    pool, id, id, pool, id);
			td_safe_system(buf, B_TRUE);
		}
	}
	(void) pclose(pipe_fp);
	return;
}

/*
 * td_be_list() - find all Solaris BEs and register them
 * calls add_td_discovered_obj(TD_OT_OS, onvl) to add to list of discovered OSs
 */
void
td_be_list()
{
	char *be_name;
	int berc;
	be_node_list_t *be_nodes, *be_node;
	char templatebe[] = TEMPLATEBE;
	char *tmpbemp = NULL;
	int err;

	/* import any root pools */
	import_any_zpools();

	/* list any BEs from reported root pools */
	berc = be_list(NULL, &be_nodes);
	if (berc != 0) {
		ls_write_log_message(TDMOD,
		    "Listing of boot environments (be_list) failed. code=%d\n",
		    berc);
		return;
	}
	for (be_node = be_nodes; be_node != NULL;
	    be_node = be_node->be_next_node) {
		nvlist_t *be = NULL;

		char inst_release_path[MAXPATHLEN];
		char release[MAXPATHLEN];
		char slicenm[MAXPATHLEN];
		char *be_mp;
		nvlist_t *onvl;
		boolean_t was_be_mounted = B_FALSE;
#ifndef INST_RELEASE_PENDING
		FILE *instrelfp;
#endif

		ls_write_dbg_message(TDMOD, LS_DBGLVL_INFO,
		    "node name=%s next=%p\n", be_node->be_node_name,
		    be_node->be_next_node);
		if (be_node->be_mounted)
			be_mp = be_node->be_mntpt;
		else {
			/* temp mount point */
			if (tmpbemp == NULL)
				tmpbemp = mkdtemp(templatebe);
			be_mp = tmpbemp;
		}
		ls_write_dbg_message(TDMOD, LS_DBGLVL_INFO,
		    "calling mkbe node=%s \n", be_node->be_node_name);
		/* be_node->be_rpool */
		if ((be = mkbe(be_node->be_node_name, be_mp)) == NULL)
			continue;
		ls_write_dbg_message(TDMOD, LS_DBGLVL_INFO,
		    "attempting to mount BE %s at %s\n",
		    be_node->be_node_name, be_mp);
		if (!be_node->be_mounted && be_mount(be) == 0) {
			was_be_mounted = B_TRUE;
			ls_write_dbg_message(TDMOD, LS_DBGLVL_INFO,
			    "mounted BE at %s\n", be_mp);
		} else
			ls_write_dbg_message(TDMOD, LS_DBGLVL_INFO,
			    "BE mount failed\n");
		/* get rootfs device name of zfs pool */
		if (!get_rpool_devname(be_node->be_rpool,
		    slicenm, sizeof (slicenm))) {
			ls_write_dbg_message(TDMOD, LS_DBGLVL_WARN,
			     "Failed to find device name of BE %s\n",
			     be_node->be_rpool);
			goto umount;
		}

#ifdef INST_RELEASE_PENDING
		strcpy(release, "OpenSolaris LiveCD");
#else
		/* get INST_RELEASE from BE */
		(void) strcpy(inst_release_path, be_mp);
		(void) strlcat(inst_release_path,
		    "/var/snadm/system/admin/INST_RELEASE",
		    sizeof(inst_release_path));
		if ((instrelfp = fopen(inst_release_path, "r")) == NULL) {
			/* TODO */
			goto umount;
		}
		if ((fgets(release, sizeof(release), instrelfp)) == NULL ||
		    release[0] == '\0') {	/* TODO */
			strcpy(release, "OpenSolaris Live CD");
		} else release[strlen(release) - 1] = '\0'; /* trailing NL */
		(void) fclose(instrelfp);
#endif
		/* BE Instance found! */
		if (nvlist_alloc(&onvl, NV_UNIQUE_NAME, 0) != 0) {
			ls_write_dbg_message(TDMOD, LS_DBGLVL_ERR,
			    "nvlist allocation failure\n");
			goto umount;
		}	/* allocate list */
		/* release string */
		if (nvlist_add_string(onvl, TD_OS_ATTR_BUILD_ID,
			    release) != 0) {
				ls_write_dbg_message(TDMOD, LS_DBGLVL_ERR,
				    "nvlist add_string failure\n");
				nvlist_free(onvl);
				goto umount;
		}
		/* add slice name to attribute list */
		if (nvlist_add_string(onvl, TD_OS_ATTR_SLICE_NAME, slicenm)
		    != 0) {
			ls_write_dbg_message(TDMOD, LS_DBGLVL_ERR,
			    "nvlist add_string failure\n");
			nvlist_free(onvl);
			goto umount;
		}

		/* add BE to list of known Solaris instances */
		add_td_discovered_obj(TD_OT_OS, onvl);
umount:
		/* if BE not previously mounted, unmount it */
		if (was_be_mounted && be_unmount(be) != 0) {
			/* if unmount fails, directory will be busy */
			tmpbemp = NULL; /* new mountpt created if needed */
		}
	} /* for each BE */
done:
	if (tmpbemp != NULL)
		(void) rmdir(tmpbemp);
}
