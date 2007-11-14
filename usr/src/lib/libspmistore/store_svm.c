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

#pragma ident	"@(#)store_svm.c	1.10	07/10/09 SMI"


/*
 * Module:	store_svm.c
 * Group:	libspmistore
 * Description:
 */

#include <ctype.h>
#include <malloc.h>
#include <stdio.h>
#include <sys/param.h>
#include <signal.h>
#include <string.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/mkdev.h>
#include <sys/stat.h>
#include <sys/fcntl.h>
#include <sys/dkio.h>
#include <dlfcn.h>
#include <link.h>
#include <errno.h>
#include "spmistore_lib.h"
#include "spmicommon_lib.h"

static void _convert_svminfo_if_remapped(svm_info_t *);

static int (*_svm_check)(char *);
static int (*_svm_start)(char *, svm_info_t **, int);
static int (*_svm_stop)();
static int (*_svm_is_md)(char *);
static int (*_svm_get_components)(char *, svm_info_t **);
static svm_info_t *(*_svm_alloc)();
static void (*_svm_free)(svm_info_t *);

/* Global vars */

static int libsvm_opened = FALSE;
static int libsvm_attempted = FALSE;
static int svm_enabled = TRUE;

/* ---------------------- public functions ----------------------- */

/*
 * Function:	_init_lib_svm
 *
 * description: dlopens the libsvm library interfaces we need to detect
 *		and mount metadevices if it exists and sets the libsvm_opened
 *		flag
 *
 * returns:	void
 */

void
spmi_init_lib_svm() {
	void *lib;

	if (get_trace_level() > 5)
		write_status(LOGSCR, LEVEL0,
		    "SPMI_STORE_SVM : spmi_init_lib_svm() entered\n");

	if ((libsvm_opened == TRUE) || (libsvm_attempted == TRUE))
		return;

	/* don't attempt this again if it fails the first time */
	libsvm_attempted = TRUE;

	if ((lib = dlopen("/usr/snadm/lib/libsvm.so", RTLD_LAZY)) == NULL) {
		/* library does not exist, set the flag and return */
		if (get_trace_level() > 5) {
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM : spmi_init_lib_svm() "
			    "dlopen of libsvm.so failed\n");
		}
		libsvm_opened = FALSE;
		return;
	} else {
		/* we found it, so we don't need to check again */
		libsvm_opened = TRUE;
	}

	if (get_trace_level() > 5)
		write_status(LOGSCR, LEVEL0,
		    "SPMI_STORE_SVM : spmi_init_lib_svm() "
		    "dlopen succeded\n");
	/* now load the libraries */
	/* svm_check returns an int */
	_svm_check =
	    (int (*)(char *))dlsym(lib, "svm_check");
	/* svm_start returns an int */
	_svm_start =
	    (int (*)(char *, svm_info_t **, int))dlsym(lib, "svm_start");
	/* svm_stop returns an int */
	_svm_stop =
	    (int (*)())dlsym(lib, "svm_stop");
	/* svm_is_md returns an int */
	_svm_is_md =
	    (int (*)(char *))dlsym(lib, "svm_is_md");
	/* svm_get_components returns an int */
	_svm_get_components =
	    (int (*)(char *, svm_info_t **))dlsym(lib, "svm_get_components");
	/* svm_alloc returns a pointer to a svm_info_t */
	_svm_alloc =
	    (svm_info_t *(*)())dlsym(lib, "svm_alloc");
	/* svm_free returns a void */
	_svm_free =
	    (void (*)(svm_info_t *))dlsym(lib, "svm_free");

	if ((_svm_check == NULL) ||
	    (_svm_start == NULL) ||
	    (_svm_stop == NULL) ||
	    (_svm_is_md == NULL) ||
	    (_svm_get_components == NULL) ||
	    (_svm_alloc == NULL) ||
	    (_svm_free == NULL)) {
		if (get_trace_level() > 5)
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM : spmi_init_lib_svm() "
			    "failed to load all functions\n");
		libsvm_opened = FALSE;
		return;
	}
	if (get_trace_level() > 5)
		write_status(LOGSCR, LEVEL0,
		    "SPMI_STORE_SVM : spmi_init_lib_svm() "
		    "all functions loaded\n");
}

/*
 * Function:	spmi_svm_alloc()
 *
 * Description: wrapper around libsvm's svm_alloc()
 * Scope:	public
 * Parameters:	none
 *
 * Return:	svm_info_t * || NULL
 */
svm_info_t *
spmi_svm_alloc()
{
	spmi_init_lib_svm();
	if (libsvm_opened == FALSE)
		return (NULL);

	return ((*_svm_alloc)());
}

/*
 * Function:	spmi_svm_free()
 *
 * Description: wrapper around libsvm's svm_free()
 * Scope:	public
 * Parameters:	none
 *
 * Return:	void
 */
void
spmi_svm_free(svm_info_t *svm)
{
	if (libsvm_opened == FALSE) {
		svm = NULL;
		return;
	}
	(*_svm_free)(svm);
}

/*
 * Function:	spmi_check_for_svm
 * Description: Checks the mounted filesystem for the existence of an svm
 *		database
 * Scope:	public
 * Parameters:  mountpoint - non-NULL mount string
 *
 * Return:	SUCCESS
 *		FAILURE
 */

int
spmi_check_for_svm(char *mountpoint)
{

	/* if disabled, then we say so */
	if (!svm_enabled) {
		if (get_trace_level() > 5)
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM : svm_check(): svm disabled");
		return (FAILURE);
	}

	/* initialize the swlib */
	spmi_init_lib_svm();
	/*
	 * If no libraries, return
	 */
	if (libsvm_opened == FALSE) {
		return (FAILURE);
	}

	/*
	 * Call the svm_check function in libsvm.so
	 */
	if ((*_svm_check)(mountpoint) == 0) {
		if (get_trace_level() > 5)
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM : svm_check() on %s succeeded\n",
			    mountpoint);
		return (SUCCESS);
	}

	if (get_trace_level() > 5)
		write_status(LOGSCR, LEVEL0,
		    "SPMI_STORE_SVM : svm_check() on %s failed\n",
		    mountpoint);

	return (FAILURE);
}

/*
 * Function:	spmi_start_svm
 * Description: calls svm_start to get a root mirror running
 *		    if one exists, svm_info will be propagated.
 *
 * Scope:	public
 * Parameters:  mountpoint - non-NULL mount string
 * 		svm - initialized svm_info structure
 *		flag - flag to determine conversion of db
 *
 * Return:	SUCCESS
 *		FAILURE
 */

int
spmi_start_svm(char *mountpoint, svm_info_t **svm, int flag)
{

	int 	ret;

	if (get_trace_level() > 5) {
	    if (flag == SVM_CONV) {
		    write_status(LOGSCR, LEVEL0,
			"SPMI_STORE_SVM: svm_start(): MD flag is SVM_CONV");
	    }
	    if (flag == SVM_DONT_CONV) {
		    write_status(LOGSCR, LEVEL0,
			"SPMI_STORE_SVM: svm_start(): MD flag is SVM_DONTCONV");
	    }
	}

	/*
	 * Start the SVM on the mounted device.
	 */
	if ((ret = (*_svm_start)(mountpoint, svm, flag)) != 0) {
		if (get_trace_level() > 5) {
			write_status(LOGSCR, LEVEL0,
		"SPMI_STORE_SVM: svm_start(): failed with %d\n", ret);
		}
		return (FAILURE);
	}

	/*
	 * Check what was returned from svm_start to make sure
	 * the device has not changed locations
	 * Use _map_to_effective_dev()
	 */

	_convert_svminfo_if_remapped(*svm);

	if (get_trace_level() > 5) {
		if (*svm != NULL && (*svm)->count > 0)
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM: started SVM on %s, using %s\n",
			    mountpoint, (*svm)->root_md);
		else
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM: started SVM, no root mirror "
			    "found on %s\n", mountpoint);
	}

	return (SUCCESS);
}

/*
 * Function:	spmi_stop_svm
 * Description: stops the metadevice
 * Scope:	public
 * Parameters:  rootdir - mountpoint of "/"
 *		svm_info - structure that will contain the svm info found
 *
 * Return:	SUCCESS
 *		FAILURE
 */

int
spmi_stop_svm(char *device, char *mountpoint)
{
	int ret;

	(void) remount_ctds(mountpoint, device);

	/* end work around */

	if ((ret = (*_svm_stop)()) != 0) {
		if (get_trace_level() > 5) {
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM : svm_stop(): failed with %d\n",
			    ret);
		}
		return (FAILURE);
	}

	if (get_trace_level() > 5) {
		write_status(LOGSCR, LEVEL0,
		    "SPMI_STORE_SVM : svm_stop(): succeeded\n");
	}

	return (SUCCESS);
}

/*
 * Function:	remount_svm
 * Description: Trys to mount the metadevice on the mountpoint
 * Scope:	public
 * Parameters:  mountpoint - non-NULL path string
 *		svm- non-NULL structure that will contain the svm info
 *		mntopt - flag to determine mounting ro or rw.
 *
 * Return:	SUCCESS
 *		FAILURE
 */

int
remount_svm(char *mountpoint, svm_info_t *svm, char *mntopts)
{
	char cmd[MAXPATHLEN];
	char options[MAXPATHLEN];

	if ((mntopts == NULL) || (strcmp(mntopts, "-") == 0)) {
		options[0] = '\0';
	} else {
		snprintf(options, sizeof (options), "-o %s", mntopts);
	}

	/*
	 * umount the mounted root filesystem
	 */
	snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/umount %s > /dev/null 2>&1", mountpoint);
	if (system(cmd) != 0) {
		if (get_trace_level() > 5)
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM: remount_svm() %s failed\n",
			    cmd);
		return (FAILURE);
	} else {
		/*
		 * now mount the mirror
		 */
		snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/mount -F ufs %s /dev/md/dsk/%s %s > "
		    "/dev/null 2>&1", options, svm->root_md, mountpoint);
		if (system(cmd) != 0) {
			if (get_trace_level() > 5)
				write_status(LOGSCR, LEVEL0,
				    "SPMI_STORE_SVM: remount_svm(): %s "
				    "failed\n", cmd);
			return (FAILURE);
		}
	}

	if (get_trace_level() > 5)
		write_status(LOGSCR, LEVEL0,
		    "SPMI_STORE_SVM : remount_svm(): Mounted "
		    "/dev/md/dsk/%s on %s\n", svm->root_md, mountpoint);
	return (SUCCESS);
}

/*
 * Function:	remount_ctds
 * Description: Trys to mount the metadevice on the mountpoint
 * Scope:	public
 * Parameters:  mountpoint - non-NULL path string
 *		device - non-NULL path string of boot device
 *
 * Return:	SUCCESS
 *		FAILURE
 */

int
remount_ctds(char *mountpoint, char *device) {

	char cmd[MAXPATHLEN];

	/*
	 * umount the mountpoint
	 */
	snprintf(cmd, sizeof (cmd),
		"/usr/sbin/umount %s > /dev/null 2>&1", mountpoint);
	if (system(cmd) != 0) {
		if (get_trace_level() > 5)
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM : umount of % failed\n",
			    mountpoint);
		return (FAILURE);
	} else {
		/*
		 * mount the ctds so upgrade can continue
		 */
		if (UfsMount(device, mountpoint, "-r") < 0 &&
		    FsMount(device, mountpoint, "-r", NULL)) {
			if (get_trace_level() > 5)
				write_status(LOGSCR, LEVEL0,
				    "SPMI_STORE_SVM : mount % on %s failed\n",
				    mountpoint);
			return (FAILURE);
		}
	}

	if (get_trace_level() > 5)
		write_status(LOGSCR, LEVEL0,
		    "SPMI_STORE_SVM : Re-mounted %s on %s\n",
		    device, mountpoint);

	return (SUCCESS);
}

/*
 * Function:	sliceExistsInSvm
 * Description: Looks at rootslice to see if it exists in svminfo
 * Scope:	public
 * Parameters:  rootslice - non-NULL cXtXdXsX string
 *		svminfo- non-NULL structure that will contain the svm info
 *
 * Return:	TRUE
 *		FALSE
 */

int
sliceExistsInSvm(char *rootslice, svm_info_t *svm) {

	int i;
	int l;
	if (rootslice == NULL || svm == NULL)
		return (FALSE);
	l = strlen(rootslice);
	for (i = 0; i < svm->count; i++) {
		if (strncasecmp(rootslice, svm->md_comps[i], l) == 0)
			return (TRUE);
	}

	return (FALSE);
}

/*
 * Function:	  getSvmSliceList
 * Description:   Looks at the components of the metadevice contained
 *		  in svminfo and returns generates a char array
 *		  based on the components
 *
 * Scope:	  public
 * Parameters:    svminfo -  pointer to a svm_info_t structure.
 *
 * Return:	  char array of svm components, seperated by a space.
 */
char *
getSvmSliceList(svm_info_t *svminfo)
{
	int i;
	char *buf;
	buf = (char *)xmalloc(MAXPATHLEN+1);
	memset(buf, sizeof (buf), 0);
	for (i = 0; i < svminfo->count; i++) {
		if (i == 0) {
			snprintf(buf, MAXPATHLEN, "%s", svminfo->md_comps[i]);
		} else {
			snprintf(buf, MAXPATHLEN, "%s %s", buf,
			    svminfo->md_comps[i]);
		}
		/*
		 * only put 2 in the list
		 * and add ... to the end.
		 */
		if (i == 2) {
			snprintf(buf, MAXPATHLEN, "%s ...", buf);
			break;
		}
	}
	return (buf);
}

/*
 * Function:		isMeta
 * Description: 	determines whether a path points to a metadevice
 * Scope:		public
 * Parameters:  	path - char array pointing to a path.
 *
 * Return:		TRUE - if it does
 * 			FALSE - if it does not
 */
int
isMeta(char *path)
{
	/*
	 * is_metadevice returns 0 if not a metedevice and
	 * 1 if it is
	 */
	spmi_init_lib_svm();
	/*
	 * If no libraries, return
	 */
	if (libsvm_opened == FALSE) {
		return (FALSE);
	}

	if ((*_svm_is_md)(path) == 1) {
		if (get_trace_level() > 5)
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM: isMeta(): true on %s", path);
		return (TRUE);
	} else {
		if (get_trace_level() > 5)
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM: isMeta(): false on %s", path);
		return (FALSE);
	}

}

/*
 * Function:		getSmallestMetaComp
 * Description: 	gets the smallest ctds in the metadevice
 * Scope:		public
 * Parameters:  	md_path -  /dev/md/dsk/<md_id>
 *
 * Return:		psmallest - device path of the smallest component
 *			do not free this, it is used by the calling function
 */
char *
getSmallestMetaComp(char *path)
{
	int		cursize = 0;
	int		tmpsize = 0;
	int		i;
	int		slice;
	char		device[MAXPATHLEN];
	char		*psmallest = NULL;
	Disk_t 		*dp;
	int 		first = 1;
	svm_info_t 	*svminfo;

	svminfo = spmi_svm_alloc();
	device[0] = '\0';

	if (get_trace_level() > 5)
		write_status(LOGSCR, LEVEL0,
		    "SPMI_STORE_SVM: getSmallestMetaComp(): path : %s", path);

	if ((*_svm_get_components)(path, &svminfo) == SUCCESS) {
		if (get_trace_level() > 5)
			write_status(LOGSCR, LEVEL0,
			    "SPMI_STORE_SVM: getSmallestMetaComp() returned "
			    "from svm_get_components");
		/*
		 * Start checking each component
		 */
		/*
		 * Check what was returned from svm_start to make sure
		 * the device has not changed locations
		 * Use _map_to_effective_dev()
		 */

		_convert_svminfo_if_remapped(svminfo);

		for (i = 0; i < svminfo->count; i++) {
			snprintf(device, sizeof (device),
			    "/dev/dsk/%s", svminfo->md_comps[i]);
			WALK_DISK_LIST(dp) {
				if (disk_not_okay(dp))
					continue;
				if (strstr(device, disk_name(dp)) == 0)
					continue;
				slice = atoi(device + (strlen(device) - 1));
				tmpsize =
				    blocks2size(dp,
						orig_slice_size(dp, slice), 1);
				if (get_trace_level() > 5)
					write_status(LOGSCR, LEVEL0,
					    "SPMI_STORE_SVM: "
					    "getSmallestMetaComp(): "
					    "device : %s - size : %d",
					    device, tmpsize);
				break;
			}
			if (first) {
				cursize = tmpsize;
				psmallest = xstrdup(device);
				first = 0;
			} else if (tmpsize < cursize) {
				cursize = tmpsize;
				psmallest = xstrdup(device);
			}
		}
	}
	spmi_svm_free(svminfo);

	if (get_trace_level() > 5)
		write_status(LOGSCR, LEVEL0,
		    "SPMI_STORE_SVM: getSmallestMetaComp(): returning %s\n",
		    psmallest);

	return (psmallest);
}

/*
 * Function:		_convert_svminfo_if_remapped
 * Description: 	converts the components of an svm_info_t to the
 *			correct device mapping for the miniroot
 *			calls _map_to_effective_dev()
 * Scope:		private
 * Parameters:  	svm_info_t
 *
 * Return:		void
 */
static void
_convert_svminfo_if_remapped(svm_info_t *svm)
{
	int 	i;
	char	tmpdev[MAXPATHLEN];
	char	emnt[MAXPATHLEN];

	if (svm != NULL && svm->count > 0) {
		for (i = 0; i < svm->count; i++) {
			snprintf(tmpdev, MAXPATHLEN, "/dev/rdsk/%s",
			    svm->md_comps[i]);
			if (_map_to_effective_dev(tmpdev, emnt) == 0) {
				free(svm->md_comps[i]);
				svm->md_comps[i] =
				    xstrdup(emnt+strlen("/dev/rdsk/"));
			}
		}
	}
}

/*
 * Function:		svm_set_enabled
 * Description: 	Enables or disables the usage of the SVM
 *		subsystem.
 * Scope:		public
 * Parameters:  	enabled - Whether to enable SVM or not during
 *		upgrade.  If it is disabled, then spmi_check_for_svm
 *		will always return false.
 *
 */
int
svm_set_enabled(int flag)
{
	svm_enabled = flag;
}
