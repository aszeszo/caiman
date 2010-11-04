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
 * Copyright (c) 2007, 2010, Oracle and/or its affiliates. All rights reserved.
 */

#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <stropts.h>

#include <sys/types.h>

#include <sys/dkio.h>
#include <sys/vtoc.h>

#include <sys/stat.h>
#include <fcntl.h>

#include <sys/nvpair.h>
#include <td_dd.h>
#include <td_api.h>
#include <td_zpool.h>

#include <ls_api.h>

/* local typedefs */

/*
 * list of possible targets, which can
 * be discovered
 */

typedef enum {
	REPORT_DISK,
	REPORT_PART,
	REPORT_SLICE,
	REPORT_OS,
	REPORT_ZPOOL
} rep_object_t;

/*
 * The reported information is displayed
 * in the table, which is generated in
 * display_report() and <object>_show_attr()
 * functions. display_report() generates fixed
 * parts of table - header, footer and line
 * for target w/o attributes available.
 */

typedef enum {
	REPORT_HEADER = 0,
	REPORT_FOOTER,
	REPORT_BODY_NOATTR,
	REPORT_PART_END
} rep_part_t;

/*
 * There are two level of verbosity supported right
 * now when generating report - low and high
 */

typedef enum {
	REPORT_VERB_LOW = 0,
	REPORT_VERB_HIGH,
	REPORT_VERB_END
} rep_verbosity_t;

/* local constants */

/* disk report */

static const char *report_disk[REPORT_PART_END][REPORT_VERB_END] = {
/* header */
{
	"---------------------------------\n"
	" num |    name|  ctype|size [MB]|\n"
	"---------------------------------\n",

	"-----------------------------------------"
	"-----------------------------------------------\n"

	" num |    name|    vendor|  ctype| mtype|"
	" rem| lbl| bsize|#of blocks|size [MB]| volname|\n"

	"-----------------------------------------"
	"-----------------------------------------------\n",
},

/* footer */
{
	"---------------------------------\n",

	"-----------------------------------------"
	"-----------------------------------------------\n",
},

/* disk w/o attributes */
{
/*	"    name|  ctype|size [MB]|  " */
	"      - |     - |       - |\n",

/*	"    name|    vendor|  ctype| mtype| rem| " */
	"      - |        - |     - |    - |  - | "

/*	"lbl| bsize|#of blocks|size [MB]|  volname|" */
	" - |    - |        - |       - |       - |\n"
}
};

/* partition report */

static const char *report_part[REPORT_PART_END][REPORT_VERB_END] = {
/* header */
{
"-------------------------------------\n"
" num |        name| active| ID| lswp|\n"
"-------------------------------------\n",

"-----------------------------------------------------------------------------\
---\n"
" num |        name| active| ID| lswp| 1st block|#of blocks|size [MB]| type \n"
"-----------------------------------------------------------------------------\
---\n",
},

/* footer */
{
"-------------------------------------\n",
"-----------------------------------------------------------------------------\
---\n",
},

/* partition w/o attributes */
{
/*	"        name| active| ID| lswp|  " */
	"          - |     - | - |   - |\n",

/*	"        name| active| ID| lswp| 1st block|#of blocks|size [MB]|  " */
	"          - |     - | - |   - |        - |        - |       - |\n"
}
};

/* slice report */

static const char *report_slice[REPORT_PART_END][REPORT_VERB_END] = {
/* header */
{
	"---------------------------------------------\n"
	" num |       name|           last mountpoint|\n"
	"---------------------------------------------\n",

	"-----------------------------------------------------------------"
	"--------------------------\n"
	" num |       name| idx| flg| tag| 1st block|#of blocks|size [MB]|"
	"      inuse by|      inuse|\n"

	"-----------------------------------------------------------------"
	"--------------------------\n"
},

/* footer */
{
	"---------------------------------------------\n",
	"-----------------------------------------------------------------"
	"--------------------------\n"
},

/* slice w/o attributes */
{
/*	"       name|           last mountpoint|  " */
	"         - |                        - |\n",

/*	"       name| idx| flg| tag| 1st block|#of blocks|size [MB]|  " */
	"         - |  - |  - |  - |        - |        - |       - |"
/*	"      inuse by|      inuse|  " */
	"            - |         - |\n"
}
};

/* Solaris instance report */

static const char *report_os[REPORT_PART_END][REPORT_VERB_END] = {
/* header */
{
	"--------------------\n"
	" num |       slice |\n"
	"--------------------\n",

	"--------------------\n"
	" num |       slice |\n"
	"--------------------\n",
},

/* footer */
{
	"--------------------\n",
	"--------------------\n",
},

/* Solaris instance w/o attributes */
{
/*	" num |       slice |  " */
	"   - |           - |\n",

/*	" num |       slice |  " */
	"   - |           - |\n",
},
};

static const char *report_zpool[REPORT_PART_END][REPORT_VERB_END] = {
/* header */
{
	"--------------------------------------------------------------------------------\n"
	" num |           name/guid/bootfs/import|    health|     size| cap%| state| ver|\n"
	"--------------------------------------------------------------------------------\n",

	"--------------------------------------------------------------------------------\n"
	" num |           name/guid/bootfs/import|    health|     size| cap%| state| ver|\n"
	"--------------------------------------------------------------------------------\n",
},

/* footer */
{
	"--------------------------------------------------------------------------------\n",
	"--------------------------------------------------------------------------------\n",
},

/* zpool instance w/o attributes */
{
/*	" num |           name/guid/bootfs/import|    health|     size| cap%| state| ver|\n" */
	"     |                                  |          |         |     |      |    |\n",

/*	" num |           name/guid/bootfs/import|    health|     size| cap%| state| ver|\n" */
	"     |                                  |          |         |     |      |    |\n",
},
};
/* local variables */

static char	*root_slice_name = "";

/*
 * display_help()
 */
static void
display_help(void)
{
	/* discovery of fdisk partitions is not supported on Sparc */

#ifdef sparc
	(void) printf("usage: test_dd [-x level] [-v] [-d] [-s all]"
	    "[-o all] [-z all]\n");
#else
	(void) printf("usage: test_dd [-x level] [-v] [-d] [-p all]"
	    "[-o all] [-z all] [-s all]\n");
#endif
}

/*
 * display_report()
 */
static void
display_report(rep_object_t obj, rep_part_t part, rep_verbosity_t verb)
{
	switch (obj) {
	case REPORT_DISK:
		(void) printf("%s", report_disk[part][verb]);
		break;

	case REPORT_PART:
		(void) printf("%s", report_part[part][verb]);
		break;

	case REPORT_SLICE:
		(void) printf("%s", report_slice[part][verb]);
		break;

	case REPORT_OS:
		(void) printf("%s", report_os[part][verb]);
		break;

	case REPORT_ZPOOL:
		(void) printf("%s", report_zpool[part][verb]);
		break;
	}
}

/*
 * disk_show_attr()
 */
static void
disk_show_attr(nvlist_t	*attrs, rep_verbosity_t verbosity)
{

	uint64_t	ui64;
	uint32_t	ui32, b;
	char		*name;

	/* drive name & current boot disk */

	if (nvlist_lookup_string(attrs, TD_DISK_ATTR_NAME, &name) == 0) {
		if (nvlist_lookup_boolean(attrs, TD_DISK_ATTR_CURRBOOT) == 0) {
			(void) printf("*%7s|", name);
		} else {
			(void) printf("%8s|", name);
		}
	} else {
		(void) printf("%8s|", "- ");
	}

	/* manufacturer - only in verbose mode */

	if (verbosity > REPORT_VERB_LOW) {
		if (nvlist_lookup_string(attrs, TD_DISK_ATTR_VENDOR, &name)
		    == 0) {
			(void) printf("%10s|", name);
		} else {
			(void) printf("%10s|", "- ");
		}
	}

	/* disk type - ata,usb,scsi,fiber channel */

	if (nvlist_lookup_string(attrs, TD_DISK_ATTR_CTYPE, &name) == 0) {
		(void) printf("%7s|", name);
	} else {
		(void) printf("%7s|", "- ");
	}

	if (verbosity > REPORT_VERB_LOW) {

		if (nvlist_lookup_uint32(attrs, TD_DISK_ATTR_MTYPE, &ui32)
		    == 0) {

			switch (ui32) {
			case TD_MT_FIXED:
				(void) printf(" FIXED");
				break;

			case TD_MT_FLOPPY:
				(void) printf("FLOPPY");
				break;

			case TD_MT_CDROM:
				(void) printf(" CDROM");
				break;

			case TD_MT_ZIP:
				(void) printf("   ZIP");
				break;

			case TD_MT_JAZ:
				(void) printf("   JAZ");
				break;

			case TD_MT_CDR:
				(void) printf("   CDR");
				break;

			case TD_MT_CDRW:
				(void) printf("  CDRW");
				break;

			case TD_MT_DVDR:
				(void) printf("  DVDR");
				break;

			case TD_MT_DVDRAM:
				(void) printf("DVDRAM");
				break;

			case TD_MT_MO_ERASABLE:
				(void) printf("MO_ERA");
				break;

			case TD_MT_MO_WRITEONCE:
				(void) printf("MO_WR1");
				break;

			case TD_MT_AS_MO:
				(void) printf("MO_ASM");
				break;

			case TD_MT_UNKNOWN:
				(void) printf("  UNKN");
				break;

			default:
				(void) printf("  UNKN");
				break;
			}

			(void) printf("|");
		} else {
			(void) printf("%6s|", "- ");
		}

		/* removable ? */

		if (nvlist_lookup_boolean(attrs, TD_DISK_ATTR_REMOVABLE)
		    == 0) {
			(void) printf("%4s|", "Yes");
		} else {
			(void) printf("%4s|", "No");
		}

		/* label type */

		if (nvlist_lookup_uint32(attrs, TD_DISK_ATTR_LABEL, &ui32)
		    == 0) {
			char	lbl[4];
			int	ln = 0;


			if (ui32 & TD_DISK_LABEL_VTOC)
				lbl[ln++] = 'V';

			if (ui32 & TD_DISK_LABEL_GPT)
				lbl[ln++] = 'G';

			if (ui32 & TD_DISK_LABEL_FDISK)
				lbl[ln++] = 'F';

			lbl[ln] = '\0';

			if (ln != 0)
				(void) printf("%4s|", lbl);
			else
				(void) printf("%4s|", "unk");
		} else {
			(void) printf("%4s|", "- ");
		}
	}

	/* block size */

	if (nvlist_lookup_uint32(attrs, TD_DISK_ATTR_BLOCKSIZE, &b) != 0) {
		b = 0;
	}

	/* total # of blocks */

	if (nvlist_lookup_uint64(attrs, TD_DISK_ATTR_SIZE, &ui64) != 0) {
		ui64 = 0;
	}

	if (verbosity > REPORT_VERB_LOW) {
		if (b != 0) {
			(void) printf("%6ld|", (long)b);
		} else {
			(void) printf("%6s|", "- ");
		}

		if (ui64 != 0) {
			(void) printf("%10lld|", ui64);
		} else {
			(void) printf("%10s|", "- ");
		}
	}

	/* total size in [MB] */

	if (b*ui64 != 0) {
		(void) printf("%9lld|", ((uint64_t)b * ui64)/(1024 * 1024));
	} else {
		(void) printf("%9s|", "- ");
	}

	/* volume name - only in verbose mode */
	if (verbosity > REPORT_VERB_LOW) {
		if (nvlist_lookup_string(attrs, TD_DISK_ATTR_VOLNAME, &name)
		    == 0) {
			(void) printf("%8s|", name);
		} else {
			(void) printf("%8s|", "- ");
		}
	}

	(void) printf("\n");
}

/*
 * discover_disks()
 */
int
discover_disks(rep_verbosity_t verbosity)
{
	nvlist_t		*disk_attr;
	int			i, ndisks;

	if (td_discover(TD_OT_DISK, &ndisks) != 0) {
		(void) printf("Couldn't discover disks\n");

		return (-1);
	}

	/* number of disks */

	(void) printf("Total number of disks: %d\n", ndisks);

	/* list disk attributes */

	display_report(REPORT_DISK, REPORT_HEADER, verbosity);

	for (i = 0; i < ndisks; i++) {
		if (td_get_next(TD_OT_DISK) != 0) {
			(void) printf("Couldn't get next disk\n");

			return (-1);
		}

		(void) printf("%4d |", i + 1);

		disk_attr = td_attributes_get(TD_OT_DISK);

		if (disk_attr == NULL) {
			display_report(REPORT_DISK, REPORT_BODY_NOATTR,
			    verbosity);
		} else {
			(void) disk_show_attr(disk_attr, verbosity);

			nvlist_free(disk_attr);
		}
	}

	display_report(REPORT_DISK, REPORT_FOOTER, verbosity);

	return (0);
}

/*
 * part_show_attr()
 */
static void
part_show_attr(nvlist_t	*attrs, rep_verbosity_t verbosity)
{
	uint32_t	bid;
	uint32_t	ptype;
	uint32_t	part_type;
	uint32_t	pcontent;
	uint32_t	b, n;
	char		*name;

	if (nvlist_lookup_string(attrs, TD_PART_ATTR_NAME, &name) == 0) {
		(void) printf("%12s|", name);
	} else {
		(void) printf("%12s|", "- ");
	}

	if (nvlist_lookup_uint32(attrs, TD_PART_ATTR_BOOTID, &bid) == 0) {
		(void) printf("%7s|", bid & 0x80 ? "Yes" : "No");
	} else {
		(void) printf("%7s|", "- ");
	}

	if (nvlist_lookup_uint32(attrs, TD_PART_ATTR_TYPE, &ptype) == 0) {
		(void) printf(" %02X|", ptype);
	} else {
		(void) printf(" %2s|", "- ");
	}

	/* display if the partition contains Linux SWAP */

	if ((nvlist_lookup_uint32(attrs, TD_PART_ATTR_CONTENT, &pcontent)
	    == 0) && (pcontent == TD_PART_CONTENT_LSWAP)) {
		(void) printf("%5s|", "Yes");
	} else {
		(void) printf("%5s|", "No");
	}

	if (verbosity <= REPORT_VERB_LOW) {
		(void) printf("\n");

		return;
	}

	if (nvlist_lookup_uint32(attrs, TD_PART_ATTR_START, &b) == 0) {
		(void) printf("%10d|", b);
	} else {
		(void) printf("%10s|", "- ");
	}

	if (nvlist_lookup_uint32(attrs, TD_PART_ATTR_SIZE, &n) == 0) {
		(void) printf("%10d|%9d|", n, n/(2*1024));
	} else {
		(void) printf("%10s|%9s|", "- ", "- ");
	}

	/* Identify the type of partition */
	if (nvlist_lookup_uint32(attrs, TD_PART_ATTR_PART_TYPE,
	    &part_type) == 0) {

		switch (part_type) {

			case TD_PART_ATTR_PART_TYPE_PRIMARY:
				(void) printf(" %10s|", "primary");
				break;

			case TD_PART_ATTR_PART_TYPE_EXT:
				(void) printf(" %10s|", "extended");
				break;


			case TD_PART_ATTR_PART_TYPE_LOGICAL:
				(void) printf(" %10s|", "logical");
				break;

			default:
				(void) printf("%10s|", "- ");
				break;
		}

	} else {
		(void) printf("%10s|", "- ");
	}

	(void) printf("\n");
}

/*
 * discover_partitions()
 */
static int
discover_partitions(char *name, rep_verbosity_t verbosity)
{
	nvlist_t	*part_attr;
	int		i;
	int		nparts;

	/*
	 * for now, only discovery of all partitions
	 * is supported
	 */

	assert(name == NULL);

	if (td_discover(TD_OT_PARTITION, &nparts) != 0) {
		(void) printf("Couldn't discover partitions\n");

		return (-1);
	}

	/* list partition attributes */

	display_report(REPORT_PART, REPORT_HEADER, verbosity);

	for (i = 0; i < nparts; i++) {
		if (td_get_next(TD_OT_PARTITION) != 0) {
			(void) printf("Couldn't get next partition\n");

			return (-1);
		}

		(void) printf("%4d |", i + 1);

		part_attr = td_attributes_get(TD_OT_PARTITION);

		if (part_attr == NULL) {
			display_report(REPORT_PART, REPORT_BODY_NOATTR,
			    verbosity);
		} else {
			(void) part_show_attr(part_attr, verbosity);

			nvlist_free(part_attr);
		}
	}

	display_report(REPORT_PART, REPORT_FOOTER, verbosity);

	return (0);
}

/*
 * slice_show_attr()
 */
static int
slice_show_attr(nvlist_t *attrs, rep_verbosity_t verbosity)
{
	uint64_t	start = 0;
	uint64_t	size = 0;
	uint32_t	ui32;
	char		*inuse;
	char		*usedby;
	char		*name;
	int		errp;

	if (nvlist_lookup_string(attrs, TD_SLICE_ATTR_NAME, &name) == 0) {
		(void) printf("%11s|", name);
	} else {
		(void) printf("%11s|", "- ");
	}

	/* discover root slice for SVM stuff */

	if (strcmp(root_slice_name, name) == 0) {
		(void) ddm_slice_inuse_by_svm(root_slice_name, attrs, &errp);
	}

	if (verbosity <= REPORT_VERB_LOW) {
		if (nvlist_lookup_string(attrs, TD_SLICE_ATTR_LASTMNT, &name)
		    == 0) {
			(void) printf("%26s|\n", name);
		} else {
			(void) printf("%26s|\n", " ");
		}

		return (0);
	}

	if (nvlist_lookup_uint32(attrs, TD_SLICE_ATTR_INDEX, &ui32) == 0) {
		(void) printf("%4d|", ui32);
	} else {
		(void) printf("%4s|", "- ");
	}

	if (nvlist_lookup_uint32(attrs, TD_SLICE_ATTR_FLAG, &ui32) == 0) {
		(void) printf("  %02lX|", (long)ui32);
	} else {
		(void) printf("%4s|", "- ");
	}

	if (nvlist_lookup_uint32(attrs, TD_SLICE_ATTR_TAG, &ui32) == 0) {
		(void) printf("  %02lX|", (long)ui32);
	} else {
		(void) printf("%4s|", "- ");
	}

	if (nvlist_lookup_uint64(attrs, TD_SLICE_ATTR_START, &start) == 0) {
		(void) printf("%10lld|", start);
	} else {
		(void) printf("%10s|", "- ");
	}

	if (nvlist_lookup_uint64(attrs, TD_SLICE_ATTR_SIZE, &size) == 0) {
		(void) printf("%10lld|", size);
	} else {
		(void) printf("%10s|", "- ");
	}

	if (size != 0) {
		(void) printf("%9lld|", size/(2*1024));
	} else {
		(void) printf("%9s|", "- ");
	}

	if (nvlist_lookup_string(attrs, TD_SLICE_ATTR_USEDBY, &usedby) == 0) {
		(void) printf("%14s|", usedby);
	} else {
		(void) printf("%14s|", "- ");
	}

	if (nvlist_lookup_string(attrs, TD_SLICE_ATTR_INUSE, &inuse) == 0) {
		(void) printf("%11s|", inuse);
	} else {
		(void) printf("%11s|", "- ");
	}

	(void) printf("\n");

	/* device ID */

	return (0);
}

/*
 * discover_slices()
 */
static int
discover_slices(rep_verbosity_t verbosity)
{
	nvlist_t	*slice_attr;
	int		i;
	int		nslices;

	if (td_discover(TD_OT_SLICE, &nslices) != 0) {
		(void) printf("Couldn't discover slices\n");

		return (-1);
	}

	/* if there is no slice, do not display empty table */

	if (nslices == 0)
		return (0);

	/* list slice attributes */

	display_report(REPORT_SLICE, REPORT_HEADER, verbosity);

	for (i = 0; i < nslices; i++) {
		if (td_get_next(TD_OT_SLICE) != 0) {
			(void) printf("Couldn't get next slice\n");

			return (-1);
		}

		(void) printf("%4d |", i + 1);

		slice_attr = td_attributes_get(TD_OT_SLICE);

		if (slice_attr == NULL) {
			display_report(REPORT_SLICE, REPORT_BODY_NOATTR,
			    verbosity);
		} else {
			(void) slice_show_attr(slice_attr, verbosity);

			nvlist_free(slice_attr);
		}
	}

	display_report(REPORT_SLICE, REPORT_FOOTER, verbosity);

	return (0);
}

/*
 * os_show_attr()
 */
static void
os_show_attr(nvlist_t *attrs)
{
	char		*name;

	if (nvlist_lookup_string(attrs, TD_OS_ATTR_SLICE_NAME, &name) == 0) {
		(void) printf("%13s|", name);
	} else {
		(void) printf("%13s|", "- ");
	}

	(void) printf("\n");
}

/*
 * discover_os()
 */
static int
discover_os(rep_verbosity_t verbosity)
{
	nvlist_t	*os_attr;
	int		i;
	int		nos;

	if (td_discover(TD_OT_OS, &nos) != 0) {
		(void) printf("Couldn't discover Solaris instances\n");

		return (-1);
	}

	/* if there is no Solaris, do not display empty table */

	if (nos == 0)
		return (0);

	/* list os attributes */

	display_report(REPORT_OS, REPORT_HEADER, verbosity);

	for (i = 0; i < nos; i++) {
		if (td_get_next(TD_OT_OS) != 0) {
			(void) printf("Couldn't get next os\n");

			return (-1);
		}

		(void) printf("%4d |", i + 1);

		os_attr = td_attributes_get(TD_OT_OS);

		if (os_attr == NULL) {
			display_report(REPORT_OS, REPORT_BODY_NOATTR,
			    verbosity);
		} else {
			(void) os_show_attr(os_attr);

			nvlist_free(os_attr);
		}
	}

	display_report(REPORT_OS, REPORT_FOOTER, verbosity);

	return (0);
}

/*
 * td_zpool_show_target()
 */
static void
td_zpool_show_target(nvlist_t *target,
	int depth,
	boolean_t is_spare)
{
	nvlist_t **targets;
	int cnt1 = 0;
	char *str;
	uint64_t ui64;
	uint32_t ui32;
	uint_t ret;

	if (target == NULL) {
		return;
	}

	if (nvlist_lookup_string(target,
	    TD_ZPOOL_ATTR_TARGET_NAME, &str) != 0) {
		(void) printf(
		    "     |   %*s%-*s",
		    depth, "", 31 - depth, "- ");
	} else {
		(void) printf(
		    "     |   %*s%-*s",
		    depth, "", 31 - depth, str);
	}

	if (nvlist_lookup_string(target,
	    TD_ZPOOL_ATTR_TARGET_HEALTH, &str) != 0) {
		(void) printf(
		    "| %9s|         ", "- ");
	} else {
		(void) printf(
		    "| %9s|         ", str);
	}

	if (is_spare == B_TRUE) {
		(void) printf("| %4s| %5s| %3s|\n", "- ", "- ", "- ");
	} else {
		if (nvlist_lookup_uint64(target,
		    TD_ZPOOL_ATTR_TARGET_READ_ERRORS, &ui64) != 0) {
			(void) printf("| %4s", "- ");
		} else {
			(void) printf("| %4llu", ui64);
		}

		if (nvlist_lookup_uint64(target,
		    TD_ZPOOL_ATTR_TARGET_WRITE_ERRORS, &ui64) != 0) {
			(void) printf("| %5s", "- ");
		} else {
			(void) printf("| %5llu", ui64);
		}

		if (nvlist_lookup_uint64(target,
		    TD_ZPOOL_ATTR_TARGET_CHECKSUM_ERRORS, &ui64) != 0) {
			(void) printf("| %3s|\n", "- ");
		} else {
			(void) printf("| %3llu|\n", ui64);
		}
	}

	if (nvlist_lookup_uint32(target,
	    TD_ZPOOL_ATTR_NUM_TARGETS,
	    &ui32) != 0) {
		return;
	}

	if (ui32 > 0) {
		if (nvlist_lookup_nvlist_array(target,
		    TD_ZPOOL_ATTR_TARGETS,
		    &targets, &ret) != 0) {
			return;
		}

		for (cnt1 = 0; cnt1 < ret; cnt1++) {
			td_zpool_show_target(targets[cnt1],
			    depth + 2, is_spare);
		}
	}
}


/*
 * td_zpool_show_attr()
 */
static void
td_zpool_show_attr(nvlist_t *attrs, rep_verbosity_t verbosity)
{
	char *str;
	uint32_t ui32;
	uint64_t ui64;
	uint32_t num_targets = 0, num_logs = 0;
	uint32_t num_l2cache = 0, num_spares = 0;
	nvlist_t **targets, **logs, **l2cache, **spares;
	int cnt1 = 0;
	uint_t ret;
	boolean_t import = B_FALSE;

	if (nvlist_lookup_string(attrs, TD_ZPOOL_ATTR_NAME, &str) == 0) {
		(void) printf(" %-33s| ", str);
	} else {
		(void) printf(" %-33s| ", "- ");
	}

	if (nvlist_lookup_string(attrs, TD_ZPOOL_ATTR_HEALTH, &str) == 0) {
		(void) printf("%9s| ", str);
	} else {
		(void) printf("%9s| ", "- ");
	}

	if (nvlist_lookup_uint64(attrs, TD_ZPOOL_ATTR_SIZE, &ui64) == 0) {
		double size_mb = 0, size_gb = 0;

		if (ui64 > 0) {
			size_mb = BYTES_TO_MB(ui64);
		} else {
			size_mb = 0;
			size_gb = 0;
		}

		if (size_mb > MB_IN_GB) {
			size_gb = MB_TO_GB(size_mb);
			size_mb = 0;
		} else {
			size_gb = 0;
		}

		(void) printf("%7.2lf%c| ",
		    size_mb > 0 ? size_mb : size_gb,
		    size_mb > 0 ? 'M' : 'G');
	} else {
		(void) printf("%8s| ", "- ");
	}

	if (nvlist_lookup_uint64(attrs, TD_ZPOOL_ATTR_CAPACITY, &ui64) == 0) {
		(void) printf("%3llu%%| ", ui64);
	} else {
		(void) printf("%4s| ", "- ");
	}

	if (nvlist_lookup_uint32(attrs, TD_ZPOOL_ATTR_STATUS, &ui32) == 0) {
		(void) printf("%5d|", ui32);
	} else {
		(void) printf("%5s|", "- ");
	}

	if (nvlist_lookup_uint32(attrs, TD_ZPOOL_ATTR_VERSION, &ui32) == 0) {
		(void) printf("  %2d|\n", ui32);
	} else {
		(void) printf("  %2s|\n", "h ");
	}

	if (nvlist_lookup_uint64(attrs, TD_ZPOOL_ATTR_GUID, &ui64) == 0) {
		(void) printf("%4s |", "");
		(void) printf("%34llu| ", ui64);
		(void) printf("%9s| ", " ");
		(void) printf("%8s| ", " ");
		(void) printf("%4s| ", " ");
		(void) printf("%5s|", " ");
		(void) printf("  %2s|\n", " ");
	} else {
		(void) printf("%4s |", "");
		(void) printf(" %34s| ", "- ");
		(void) printf("%9s| ", " ");
		(void) printf("%8s| ", " ");
		(void) printf("%4s| ", " ");
		(void) printf("%5s|", " ");
		(void) printf("  %2s|\n", " ");
	}

	if (nvlist_lookup_string(attrs, TD_ZPOOL_ATTR_BOOTFS, &str) == 0) {
		(void) printf("%4s |", "");
		(void) printf(" %33s| ", str != NULL ? str : "m");
		(void) printf("%9s| ", " ");
		(void) printf("%8s| ", " ");
		(void) printf("%4s| ", " ");
		(void) printf("%5s|", " ");
		(void) printf("  %2s|\n", " ");
	}

	if (nvlist_lookup_boolean_value(attrs,
	    TD_ZPOOL_ATTR_IMPORT, &import) == 0) {
		if (import) {
			(void) printf("%4s |", "");
			(void) printf(" %33s| ", "Importable pool");
			(void) printf("%9s| ", " ");
			(void) printf("%8s| ", " ");
			(void) printf("%4s| ", " ");
			(void) printf("%5s|", " ");
			(void) printf("  %2s|\n", " ");
		}
	}

	if (verbosity == REPORT_VERB_HIGH) {
		/* High verbosity just print number of targets */
		num_targets = 0;
		if (nvlist_lookup_uint32(attrs, TD_ZPOOL_ATTR_NUM_TARGETS,
		    &num_targets) != 0) {
			num_targets = 0;
		}

		/* Print targets */
		if (num_targets > 0) {
			if (nvlist_lookup_nvlist_array(attrs,
			    TD_ZPOOL_ATTR_TARGETS, &targets, &ret) != 0) {
				(void) printf("     | %72s|\n",
				    "Failed to retrieve targets");
			} else {
				for (cnt1 = 0; cnt1 < ret; cnt1++) {
					td_zpool_show_target(targets[cnt1],
					    0, B_FALSE);
				}
			}
		}

		/* Print logs */
		num_logs = 0;
		if (nvlist_lookup_uint32(attrs, TD_ZPOOL_ATTR_NUM_LOGS,
		    &num_logs) != 0) {
			num_logs = 0;
		}

		if (num_logs > 0) {
			(void) printf("%4s |", "");
			(void) printf(" %-33s| ", "logs");
			(void) printf("%9s| ", " ");
			(void) printf("%8s| ", " ");
			(void) printf("%4s| ", " ");
			(void) printf("%5s|", " ");
			(void) printf("  %2s|\n", " ");

			if (nvlist_lookup_nvlist_array(attrs,
			    TD_ZPOOL_ATTR_LOGS, &logs, &ret) != 0) {
				(void) printf("     | %72s|\n",
				    "Failed to retrieve logs");
			} else {
				for (cnt1 = 0; cnt1 < ret; cnt1++) {
					td_zpool_show_target(logs[cnt1],
					    0, B_FALSE);
				}
			}
		}

		/* Print l2cache */
		num_l2cache = 0;
		if (nvlist_lookup_uint32(attrs, TD_ZPOOL_ATTR_NUM_L2CACHE,
		    &num_l2cache) != 0) {
			num_l2cache = 0;
		}

		if (num_l2cache > 0) {
			(void) printf("%4s |", "");
			(void) printf(" %-33s| ", "cache");
			(void) printf("%9s| ", " ");
			(void) printf("%8s| ", " ");
			(void) printf("%4s| ", " ");
			(void) printf("%5s|", " ");
			(void) printf("  %2s|\n", " ");

			if (nvlist_lookup_nvlist_array(attrs,
			    TD_ZPOOL_ATTR_L2CACHE, &l2cache, &ret) != 0) {
				(void) printf("     | %72s|\n",
				    "Failed to retrieve l2cache");
			} else {
				for (cnt1 = 0; cnt1 < ret; cnt1++) {
					td_zpool_show_target(l2cache[cnt1],
					    0, B_FALSE);
				}
			}
		}

		/* Print spares */
		num_spares = 0;
		if (nvlist_lookup_uint32(attrs, TD_ZPOOL_ATTR_NUM_SPARES,
		    &num_spares) != 0) {
			num_spares = 0;
		}

		if (num_spares > 0) {
			(void) printf("%4s |", "");
			(void) printf(" %-33s| ", "spares");
			(void) printf("%9s| ", " ");
			(void) printf("%8s| ", " ");
			(void) printf("%4s| ", " ");
			(void) printf("%5s|", " ");
			(void) printf("  %2s|\n", " ");

			if (nvlist_lookup_nvlist_array(attrs,
			    TD_ZPOOL_ATTR_SPARES, &spares, &ret) != 0) {
				(void) printf("     | %72s|\n",
				    "Failed to retrieve spares");
			} else {
				for (cnt1 = 0; cnt1 < ret; cnt1++) {
					td_zpool_show_target(spares[cnt1],
					    0, B_TRUE);
				}
			}
		}
	}
}

/*
 * discover_zpool()
 */
static int
discover_zpool(rep_verbosity_t verbosity)
{
	nvlist_t	*zpool_attr;
	int		i;
	int		nozpools;

	if (td_discover(TD_OT_ZPOOL, &nozpools) != 0) {
		(void) printf("Couldn't discover zpools\n");

		return (-1);
	}

	/* if there is no Solaris, do not display empty table */
	if (nozpools == 0)
		return (0);

	(void) printf("Total number of zpools: %d\n", nozpools);

	/* list os attributes */
	display_report(REPORT_ZPOOL, REPORT_HEADER, verbosity);

	for (i = 0; i < nozpools; i++) {
		if (td_get_next(TD_OT_ZPOOL) != 0) {
			(void) printf("Couldn't get next zpool\n");

			return (-1);
		}

		(void) printf("%4d |", i + 1);

		zpool_attr = td_attributes_get(TD_OT_ZPOOL);

		if (zpool_attr == NULL) {
			display_report(REPORT_ZPOOL, REPORT_BODY_NOATTR,
			    verbosity);
		} else {
			(void) td_zpool_show_attr(zpool_attr, verbosity);

			nvlist_free(zpool_attr);
		}
		display_report(REPORT_ZPOOL, REPORT_BODY_NOATTR, verbosity);
	}

	display_report(REPORT_ZPOOL, REPORT_FOOTER, verbosity);

	return (0);
}

/*
 * main()
 */
int
main(int argc, char *argv[])
{
	rep_verbosity_t	verbosity = REPORT_VERB_LOW;

	int		opt;
	int		fl_discover_disks = 0;
	int		fl_discover_parts = 0;
	char		*part_object_to_discover = NULL;
	int		fl_discover_slices = 0;
	char		*slice_object_to_discover = NULL;
	int		fl_discover_os = 0;
	char		*os_object_to_discover = NULL;
	int		fl_discover_zpools = 0;
	char		*zpool_object_to_discover = NULL;

	/* init logging/debugging service */

	ls_init(NULL);

	/*
	 * d - disk discovery
	 * p - partition discovery (not for Sparc)
	 * s - slice discovery
	 * o - discovery of Solaris instances
	 * v - verbose output
	 * z - zpool discovery
	 */

	/* -p is not supported for Sparc */

#ifdef sparc
	while ((opt = getopt(argc, argv, "x:vds:o:z:")) != EOF) {
#else
	while ((opt = getopt(argc, argv, "x:vdp:s:o:z:")) != EOF) {
#endif
		switch (opt) {

			/* display drive ID */

			/* debug level */

			case 'x': {
				/*
				 * convert from  command line option
				 * to logsvc debug level
				 */

				ls_dbglvl_t dbg_lvl = atoi(optarg) + 1;

				ls_set_dbg_level(dbg_lvl);
			}
			break;

			case 'd':
				fl_discover_disks = 1;
			break;
#ifndef sparc
			case 'p':
				fl_discover_parts = 1;

				part_object_to_discover = optarg;
			break;
#endif
			case 's':
				fl_discover_slices = 1;

				slice_object_to_discover = optarg;
			break;

			/* TODO */

			case 'o':
				fl_discover_os = 1;

				os_object_to_discover = optarg;
			break;

			case 'z':
				fl_discover_zpools = 1;

				zpool_object_to_discover = optarg;
			break;

			case 'v':
				verbosity = REPORT_VERB_HIGH;
			break;
		}
	}

	/*
	 * if there is nothing to discover, display help and exit
	 */
	if (!fl_discover_disks && !fl_discover_parts && !fl_discover_slices &&
	    !fl_discover_os && !fl_discover_zpools) {
		display_help();

		return (0);
	}

	/* discover disks */

	if (fl_discover_disks) {

		(void) printf("Disk discovery\n");

		(void) discover_disks(verbosity);

		(void) td_discovery_release();
	}

	/* discover partitions */

	if (fl_discover_parts) {
		/* determine if all partitions are to be discovered */

		if (strncmp(part_object_to_discover, "all",
		    sizeof ("all") - 1) == 0) {
			(void) printf("\nPartition discovery for all disks\n");

			(void) discover_partitions(NULL, verbosity);
		} else {
			(void) printf("\n-p <disk> not supported right now\n");
		}
	}

	/* discover slices */

	if (fl_discover_slices) {
		/* determine if we are requested to discover all slices */

		if (strncmp(slice_object_to_discover, "all",
		    sizeof ("all") - 1) == 0) {
			(void) printf("\nSlice discovery for all disks\n");

			(void) discover_slices(verbosity);
		} else {
			(void) printf("\n-s <object> not supported for now\n");
		}
	}

	/* discover Solaris instances */

	if (fl_discover_os) {
		/* determine if all Solaris instances are to be discovered */

		if (strncmp(os_object_to_discover, "all",
		    sizeof ("all") - 1) == 0) {
			(void) printf("\nLooking for all Solaris instances\n");

			(void) discover_os(verbosity);
		} else {
			(void) printf("\n-o <object> not supported for now\n");
		}
	}

	/* discover zpools */

	if (fl_discover_zpools) {
		/* determine if all zpools are to be discovered */

		if (strncmp(zpool_object_to_discover, "all",
		    sizeof ("all") - 1) == 0) {
			(void) printf("\nZpool discovery\n");

			(void) discover_zpool(verbosity);
		} else {
			(void) printf("\n-z <zpool> not supported for now\n");
		}
	}
	return (0);
}
