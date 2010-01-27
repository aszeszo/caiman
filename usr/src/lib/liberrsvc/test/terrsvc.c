/*
 * To run this test program against a local build, you should first, either:
 * A - run a nightly build, OR
 * B - do the following:
 *     - 'make install' in parent dirrectory (usr/src/lib/liberrsvc)
 *     - 'make install' in usr/src/lib/liberrsvc_pymod
 *     - 'make install' in usr/src/lib/install_utils
 *       (this is needed to create the file:
 * proto/root_i386/usr/lib/python2.6/vendor-packages/osol_install/__init__.py)
 *
 *
 * and then:
 * - export \
 * PYTHONPATH=../../../../../proto/root_i386/usr/lib/python2.6/vendor-packages
 *   (adjust "i386" for SPARC)
 * - ./terrsvc
 */

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

#include <stdio.h>
#include <string.h>

#include "../liberrsvc.h"

extern boolean_t test1();
extern boolean_t test2();
extern boolean_t test3();
extern boolean_t test4();
extern boolean_t test5();
extern boolean_t test6();
extern boolean_t test7();
extern boolean_t test8();
extern boolean_t get_err_data_int_by_type();
extern boolean_t get_err_data_str_by_type();
extern boolean_t test_get_error_type();
extern boolean_t test_get_errors_by_type();

void usage(void);

/*
 * Test harness
 */
int
main(int argc, char **argv) {
	int passes = 0;
	int fails = 0;

	printf("Testing ERROR Service (C side)\n\n");

	if (argc > 1 && argc < 8) {
		usage();
		return (1);
	} else if (argc == 8) {
		if (test_with_args(argv[1], atoi(argv[2]), atoi(argv[3]),
		    argv[4], argv[5], argv[6], argv[7])) {
			passes++;
		} else {
			fails++;
		}
	}

	if (test1()) {
		passes++;
	} else {
		fails++;
	}

	if (test2()) {
		passes++;
	} else {
		fails++;
	}

	if (test3()) {
		passes++;
	} else {
		fails++;
	}

	if (test4()) {
		passes++;
	} else {
		fails++;
	}

	if (test5()) {
		passes++;
	} else {
		fails++;
	}

	if (test6()) {
		passes++;
	} else {
		fails++;
	}

	if (test7()) {
		passes++;
	} else {
		fails++;
	}

	if (test8()) {
		passes++;
	} else {
		fails++;
	}

	if (test_get_errors_by_type()) {
		passes++;
	} else {
		fails++;
	}

	if (test_get_error_type()) {
		passes++;
	} else {
		fails++;
	}

	if (get_err_data_int_by_type()) {
		passes++;
	} else {
		fails++;
	}

	if (get_err_data_str_by_type()) {
		passes++;
	} else {
		fails ++;
	}

	if (test_get_mod_id()) {
		passes++;
	} else {
		fails++;
	}

	printf("\n\nSummary of tests\n");
	printf("================\n");
	printf("Total number of tests run:\t%d\n", (passes + fails));
	printf("Number of tests that PASSED:\t%d\n", passes);
	printf("Number of tests that FAILED:\t%d\n", fails);
	printf("\nFinished.\n");

	exit(fails);
}

void
usage(void)
{
	printf("Usage: terrsvc [mod_id, err_type, err_num, option_str, "
	    "fix_it_str, failede_at_str, failure_str]\n");

}
