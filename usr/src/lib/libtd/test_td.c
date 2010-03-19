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
 * Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
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
	REPORT_OS
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
	(void) printf("usage: test_dd [-x level] [-v] [-d] [-s all]\n");
#else
	(void) printf("usage: test_dd [-x level] [-v] [-d] [-p all]"
	    "[-s all]\n");
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

	/* init logging/debugging service */

	ls_init(NULL);

	/*
	 * d - disk discovery
	 * p - partition discovery (not for Sparc)
	 * s - slice discovery
	 * o - discovery of Solaris instances
	 * v - verbose output
	 */

	/* -p is not supported for Sparc */

#ifdef sparc
	while ((opt = getopt(argc, argv, "x:vds:o:")) != EOF) {
#else
	while ((opt = getopt(argc, argv, "x:vdp:s:o:")) != EOF) {
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

			case 'v':
				verbosity = REPORT_VERB_HIGH;
			break;
		}
	}

	/*
	 * if there is nothing to discover, display help and exit
	 */
	if (!fl_discover_disks && !fl_discover_parts && !fl_discover_slices &&
	    !fl_discover_os) {
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

	return (0);
}
