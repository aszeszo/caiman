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
 * Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


/*
 * this is a test program for Target Discovery Manager
 * for development use only
 */

#include <stdio.h>
#include <strings.h>
#include <sys/types.h>
#include <unistd.h>
#include <td_api.h>
#include <bootlog.h>
#include <libintl.h>
#include <libnvpair.h>
#include <orchestrator_api.h>

#include <ls_api.h>

static void dump_td_attributes(nvlist_t *);
char *get_object_type(td_object_type_t);

static int trace_level = LS_DBGLVL_ERR;

void
discover(td_object_type_t otype)
{
	td_errno_t tderrno;
	int nobjs, i;
	nvlist_t *attr;

	tderrno = td_discover(otype, &nobjs);
	if (tderrno != TD_E_SUCCESS) {
		(void) printf("Discovery failure %d\n", tderrno);
		return;
	}

	(void) printf("%s discovery:\n", get_object_type(otype));
	(void) printf("  %d found - getting attributes...\n", nobjs);

	td_reset(otype); /* reset enum in case of multiple calls */

	for (i = 0; i < nobjs; i++) {
		if (trace_level > LS_DBGLVL_ERR)
			(void) printf("    Discovering %s %d)\n",
			    get_object_type(otype), i);

		/* enumerate objects - set current */
		tderrno = td_get_next(otype);
		if (tderrno != TD_E_SUCCESS)
			continue;
		/* fetch attributes for current object */
		attr = td_attributes_get(otype);

		(void) printf("     %s %d)\n", get_object_type(otype), i);
		if (attr == NULL && TD_ERRNO != TD_E_SUCCESS)
			(void) printf("  discover error code = %d\n", TD_ERRNO);
		dump_td_attributes(attr);
		td_list_free(attr);
	}
}

void
test_partition_by_disk(char *pdn)
{
	int pcount;
	char *ppn;
	nvlist_t **ppart;

	(void) printf(">>> Getting partitions by disk name=%s\n", pdn);
	ppart = td_discover_partition_by_disk(pdn, &pcount);
	if (TD_ERRNO == TD_E_NO_DEVICE) {
		(void) printf("  No disk by that name found\n");
		return;
	}
	if (TD_ERRNO != TD_E_SUCCESS) {
		(void) printf("  Failed with error code %d\n", TD_ERRNO);
		return;
	}
	(void) printf(">>>     %d found\n", pcount);
	for (; pcount > 0; pcount--, ppart++) {
		if (nvlist_lookup_string(*ppart,
		    TD_PART_ATTR_NAME, &ppn) != 0)
			continue;
		(void) printf(">>>> matches partition %s\n", ppn);
		dump_td_attributes(*ppart);
	}
	(void) printf("releasing resources...\n");
	td_attribute_list_free(ppart);
	td_discovery_release();
	(void) printf("finished.\n");
}

void
test_slice_by_disk(char *pdn)
{
	int pcount;
	char *ppn;
	nvlist_t **pslice;

	(void) printf(">>> Getting slices by disk name=%s\n", pdn);
	pslice = td_discover_slice_by_disk(pdn, &pcount);
	(void) printf(">>>     %d found\n", pcount);
	for (; pcount > 0; pcount--, pslice++) {
		if (nvlist_lookup_string(*pslice,
		    TD_SLICE_ATTR_NAME, &ppn) != 0)
			continue;
		(void) printf(">>>> matches slice %s\n", ppn);
		dump_td_attributes(*pslice);
	}
	(void) printf("releasing resources...\n");
	td_attribute_list_free(pslice);
	td_discovery_release();
	(void) printf("finished.\n");
}

void
usage()
{
	(void) printf(
	    "  discovers disks, partitions, slices, Solaris instances\n"
	    "  statically built for miniroot or normal Solaris\n"
	    "  dumps all attributes of all discovered objects\n"
	    " to work properly, must be run as root\n");
	(void) printf("Usage: tdmgtst {-d | -p <disk> | -s <disk>} [-v[v]]\n"
	    " -d perform discovery on all objects and dump attributes\n"
	    " -p <disk> finds partitions on disk (cNdN|cNtNdN)\n"
	    " -s <disk> finds slices on disk (cNdN|cNtNdN)\n"
	    " -v include warning-level debugging information\n"
	    " -vv include informational-level debugging information\n"
	    " -vvv include trace-level debugging information\n");
}

void
/* LINTED [unused arg] */
tool_progress(om_callback_info_t *cb, uintptr_t arg)
{
	(void) printf("num_mile=%d curr_miles=%d type=%d pct=%d\n",
	    cb->num_milestones, cb->curr_milestone, cb->callback_type,
	    cb->percentage_done);
}

int
main(int argc, char **argv)
{
	char c;
	boolean_t go = B_FALSE;
	char *pdiskpart = NULL;
	char *pdiskslice = NULL;

	(void) printf("Caiman Target Discovery test program - Version 4\n");

	if (getuid() != 0)
		(void) printf("\n **NOTE - run as root to see all data**\n\n");
	if (strstr(argv[0], "tmt") != NULL) /* no switches needed */
		go = B_TRUE;
	while ((c = getopt(argc, argv, "dp:s:v")) != EOF) {
		switch (c) {
		case 'd':
			if (go)
				ls_set_dbg_level(++trace_level);
			go = B_TRUE;
			break;
		case 'p':
			pdiskpart = optarg;
			break;
		case 's':
			pdiskslice = optarg;
			break;
		case 'v':
			ls_set_dbg_level(++trace_level);
			break;
		default:
			usage();
			exit(1);
		}
	}
	if (pdiskpart != NULL) {
		test_partition_by_disk(pdiskpart);
		return (0);
	}
	if (pdiskslice != NULL) {
		test_slice_by_disk(pdiskslice);
		return (0);
	}
	if (!go) {
		usage();
		exit(1);
	}

	discover(TD_OT_DISK);
	discover(TD_OT_PARTITION);
	discover(TD_OT_SLICE);
	discover(TD_OT_OS);

	(void) printf("releasing resources...\n");
	td_discovery_release();
	(void) printf("finished.\n");
	return (0);
}

void
dump_upg_codes(struct td_upgrade_fail_reasons *fr)
{
	(void) printf("\n\t Upgrade failure codes:");
	if (fr->root_not_mountable)
		(void) printf("\n\t\t root_not_mountable");
	if (fr->var_not_mountable)
		(void) printf("\n\t\t var_not_mountable");
	if (fr->no_inst_release)
		(void) printf("\n\t\t no_inst_release");
	if (fr->no_cluster)
		(void) printf("\n\t\t no_cluster");
	if (fr->no_clustertoc)
		(void) printf("\n\t\t no_clustertoc");
	if (fr->no_bootenvrc)
		(void) printf("\n\t\t no_bootenvrc");
	if (fr->zones_not_upgradeable)
		(void) printf("\n\t\t zones_not_upgradeable");
	if (fr->no_usr_packages)
		(void) printf("\n\t\t no_usr_packages");
	if (fr->no_version)
		(void) printf("\n\t\t no_version");
	if (fr->svm_root_mirror)
		(void) printf("\n\t\t svm_root_mirror");
	if (fr->wrong_metacluster)
		(void) printf("\n\t\t wrong_metacluster");
	if (fr->os_version_too_old)
		(void) printf("\n\t\t os_version_too_old");
}

/*
 * dump all attributes for given Target Discovery object
 */
static void
dump_td_attributes(nvlist_t *pnvlist)
{
	nvpair_t *pnvpair = NULL;
	char *pnvname;
	int cnt = 0;
	data_type_t nvptype;

	pnvpair = NULL;
	if (pnvlist == NULL) {
		(void) printf("  [empty nvlist]\n");
		return;
	}
	while ((pnvpair = nvlist_next_nvpair(pnvlist, pnvpair)) != NULL) {
		nvptype = nvpair_type(pnvpair);
		pnvname = nvpair_name(pnvpair);
		(void) printf("           ");
		(void) printf("%s", pnvname);
		if (DATA_TYPE_STRING == nvptype) {

			char *puse = NULL;

			nvpair_value_string(pnvpair, &puse);
			(void) printf("=%s", (puse == NULL ? "none" : puse));
		} else if (DATA_TYPE_BOOLEAN == nvptype) {

			boolean_t	ibool;

			if (nvpair_value_boolean_value(pnvpair, &ibool))
				(void) printf("=%s", ibool ? "yes":"no");
			else
				(void) printf(
				    "dump_td_attributes lookup boolean failed");
		} else if (DATA_TYPE_UINT32 == nvptype) {

			uint32_t	myuint32;

			if (nvlist_lookup_uint32(pnvlist, pnvname,
			    &myuint32) == 0)
				(void) printf("=%u (uint32)", myuint32);
			else
				(void) printf(
				    "dump_td_attributes lookup int32 failed");

			if (strcmp(pnvname,
			    TD_OS_ATTR_NOT_UPGRADEABLE) == 0) {
				dump_upg_codes((struct
				    td_upgrade_fail_reasons *)&myuint32);
			}
		} else if (DATA_TYPE_UINT64 == nvptype) {

			uint64_t	myuint64;

			if (nvlist_lookup_uint64(pnvlist, pnvname,
			    &myuint64) == 0)
				(void) printf("=%lld (uint64)", myuint64);
			else
				(void) printf(
				    "dump_td_attributes lookup int64 failed");
		} else if (DATA_TYPE_STRING_ARRAY == nvptype) {

			char **p;
			uint_t len;

			if (nvlist_lookup_string_array(pnvlist, pnvname,
			    &p, &len) == 0) {
				(void) printf(" (string array) count=%u", len);
				for (; len > 0; len--, p++)
					(void) printf(
					    "\n                <%s>", *p);
			}
			else
				(void) printf(
				    "dump_td_attributes lookup string array"
				    " failed");
		} else if (DATA_TYPE_BYTE_ARRAY == nvptype) {

			uchar_t *p;
			uint_t len;

			if (nvlist_lookup_byte_array(pnvlist, pnvname,
			    &p, &len) == 0) {
				(void) printf(" (byte array) length=%u", len);
				for (; len > 0; len--, p++)
					(void) printf(" <0x%x>", *p);
			}
			else
				(void) printf(
				    "dump_td_attributes lookup string array"
				    " failed");
		} else {
			(void) printf(" unsupported data type=%d for %s",
			    nvptype, pnvname);
		}
		(void) printf("\n");
		cnt++;
	}
	if (cnt == 0) (void) printf("      [empty nvlist descriptor]\n");
}

char *
get_object_type(td_object_type_t otype)
{
	switch (otype) {
		case TD_OT_DISK: return "disk";
		case TD_OT_PARTITION: return "partition";
		case TD_OT_SLICE: return "slice";
		case TD_OT_OS: return "Solaris instance";
		default: break;
	}
	return ("");
}
