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
 * Module:	svc_kernel.c
 * Group:	libspmisvc
 * Description:
 *	Determine the characteristics of the kernel for this machine
 */

#include "spmisvc_lib.h"

/* Local functions */
static void _parse_isa(char *, int *, int *);

/*
 * Public functions
 */

/*
 * Name:	kernel_type_allowed
 * Description:	Determine whether or not a given kernel type is supported on
 *		the current system.  NOTE:  This function only supports
 *		SPARC, as only SPARC (as of this writing) is able to boot
 *		multiple kernels.
 * Scope:	public
 * Arguments:	kernel	- [RO, *RO] (char *)
 *			  The kernel type to be checked.  Currently-allowed
 *			  values are `sparc' and `sparcv9'.
 * Returns:	1	- The given kernel type is supported
 *		0	- The given kernel type is not supported
 *		-1	- An unknown kernel type was provided
 */
int
kernel_type_allowed(char *kernel)
{
	char *isa;
	int foundv7, foundv9;

	if (!(isa = get_hw_capability("ISA"))) {
		/* Fallback - both kernel types supported on all machines */
		if (streq(kernel, "sparc") ||
		    streq(kernel, "sparcv9")) {
			return (1);
		} else {
			return (-1);
		}
	}

	/*
	 * The 64-bit kernel is always supported.  The 32-bit kernel is
	 * supported only when explicitly mentioned.
	 */
	_parse_isa(isa, &foundv7, &foundv9);
	if (streq(kernel, "sparc")) {
		return (foundv7);
	} else if (streq(kernel, "sparcv9")) {
		return (1);
	} else {
		return (-1);
	}
}

/*
 * Name:	kernel_type_preferred
 * Description:	Determine whether or not a given kernel type is preferred
 *		on the current machine.  NOTE:  This function only supports
 *		SPARC, as only SPARC (as of this writing) supports multiple
 *		kernel types.
 * Scope:	public
 * Arguments:	kernel	- [RO, *RO] (char *)
 *			  The kernel type to be checked.  Currently-allowed
 *			  values are `sparc' and `sparcv9'.
 * Returns:	1	- The given kernel type is preferred
 *		0	- The given kernel type is not preferred
 *		-1	- An unknown kernel type was provided
 */
int
kernel_type_preferred(char *kernel)
{
	char *isa;
	int foundv7, foundv9;

	if (!(isa = get_hw_capability("ISA"))) {
		if (streq(get_default_machine(), "sun4u") ||
		    streq(get_default_machine(), "sun4us")) {
			return (streq(kernel, "sparcv9"));
		} else {
			return (streq(kernel, "sparc"));
		}
	}

	_parse_isa(isa, &foundv7, &foundv9);
	if (foundv7 && !foundv9) {
		/* ISA=sparc */
		return (streq(kernel, "sparc"));
	} else if (foundv7 && foundv9) {
		/* ISA=sparc,sparcv9 */
		return (streq(kernel, "sparcv9"));
	} else if (!foundv7 && foundv9) {
		/* ISA=sparcv9 */
		return (streq(kernel, "sparcv9"));
	} else {
		/* Error case */
		return (0);
	}
}

/*
 * Private functions
 */

/*
 * Name:	_parse_isa
 * Description:	Given a comma-separated list including only `sparc' and/or
 *		`sparcv9' tokens, determine which of the two types is
 *		present.
 * Scope:	private
 * Arguments:	isalist		- [RO, *RO] (char *)
 *				  The list of tokens
 *		foundv7p	- [RO, *WO] (int *)
 *				  Where a 1 or a 0 will be stored if the
 *				  `sparc' token was found or not found,
 *				  respectively.
 *		foundv9p	- [RO, *WO] (int *)
 *				  Where a 1 or a 0 will be stored if the
 *				  `sparcv9' token was found or not found,
 *				  respectively.
 * Returns:	none
 */
static void
_parse_isa(char *isalist, int *foundv7p, int *foundv9p)
{
	int foundv7, foundv9;
	char *isacopy;
	char *isa;

	isacopy = xstrdup(isalist);
	foundv7 = foundv9 = 0;
	for (isa = strtok(isacopy, ","); isa; isa = strtok(NULL, ",")) {
		if (streq(isa, "sparcv9")) {
			foundv9 = 1;
		} else if (streq(isa, "sparc")) {
			foundv7 = 1;
		}
	}
	free(isacopy);

	*foundv7p = foundv7;
	*foundv9p = foundv9;
}

#ifdef MODULE_TEST

/*
 * This test will read the capabilities from a user-specified directory and
 * will, from that, determine whether or not the system supports booting from
 * the given architectures.
 */
void
main(int argc, char **argv)
{
	char *isa;
	int rc;
	int i;

	if (argc <= 3) {
		fprintf(stderr, "Usage: %s cap_dir arch [arch] ...\n", argv[0]);
		exit(1);
	}

	set_hw_capability_dir(argv[1]);

	if ((rc = read_hw_capabilities()) != 0) {
		fprintf(stderr, "Error: read_hw_capabilities "
		    "returned %d\n", rc);
		exit(1);
	}

	for (i = 2; i < argc; i++) {
		printf("Arch: %10s: allowed %d preferred %d\n", argv[i],
		    kernel_type_allowed(argv[i]),
		    kernel_type_preferred(argv[i]));
	}
}

#endif
