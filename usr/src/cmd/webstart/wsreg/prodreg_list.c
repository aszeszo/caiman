/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */

/*
 * Copyright 2002 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)prodreg_list.c	1.2	06/02/27 SMI"

/*
 * prodreg_list.c
 *
 * Support the archaic prodreg list command line syntax.
 */

/*LINTLIBRARY*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <locale.h>
#include <wsreg.h>

#include "prodreg_cli.h"

/*
 * Returns data associated with the specified prodreg 2.0
 * attribute.  This function takes into account the mapping
 * between attributes in Prodreg 2.0 Article objects and
 * the Product Install Registry Wsreg_component structure
 * fields.
 */
static char *
get_component_attribute(Wsreg_component *comp, const char *selector)
{
	if (comp != NULL && selector != NULL) {
		if (strcmp(selector, "mnemonic") == 0) {
			return (wsreg_get_unique_name(comp));
		} else if (strcmp(selector, "version") == 0) {
			return (wsreg_get_version(comp));
		} else if (strcmp(selector, "vendor") == 0) {
			return (wsreg_get_vendor(comp));
		} else if (strcmp(selector, "installlocation") == 0) {
			return (wsreg_get_location(comp));
		} else if (strcmp(selector, "title") == 0) {
			return (wsreg_get_display_name(comp, global_lang));
		} else if (strcmp(selector, "uninstallprogram") == 0) {
			return (wsreg_get_uninstaller(comp));
		} else if (strcmp(selector, "uuid") == 0) {
			return (wsreg_get_id(comp));
		} else {
			return (wsreg_get_data(comp, selector));
		}
	}
	return (NULL);
}

/*
 * prodreg_list
 *
 * This command will walk the product registry (only, not the package
 * database.  It will list the component followed by the attribute.
 *
 * Note:  This command is only being supported in order not to break
 *   some existing install scripts (postinstall in SUNWtxfnt, and
 *   preinstall in SUNWmdr, SUNWapct, SUNWlur, and SUNWmc in Solaris 10.
 *   as the new prodreg CLI will likely be backported and previous
 *   versions of the OS may make greater use of this archaic convention
 *   it is wise to continue supporting it for some time to come, even
 *   though LSARC/2002/214 formally terminated any support for this
 *   interface on the basis of internal contracts.
 *
 *   This conforms to the prodreg 2.0 'list' command as used to find
 *   IDs associated with particular 'unique names'.
 *
 * Return: Nothing.
 * Side effects: None.
 */
void
prodreg_list(char *pcRoot, int argc,  char *argv[])
{
	int i = 0, k;
	Wsreg_component **pp = NULL;

	if (pcRoot && pcRoot[0] == '\0') pcRoot = NULL;
	if (wsreg_initialize(WSREG_INIT_NORMAL, pcRoot) != WSREG_SUCCESS) {
		fail(PRODREG_CONVERT_NEEDED_ACCESS);
	}

	if (wsreg_can_access_registry(O_RDONLY) == 0) {
		fail(PRODREG_CANNOT_READ);
	}

	if ((pp = wsreg_get_all()) == NULL)
		fail(PRODREG_FAILED);

	/* Find out which values to print */
	for (i = 0; pp[i]; i++) {
		char *pc = get_component_attribute(pp[i], argv[0]);
		char *pcv;
		if (pc) {
			for (k = 1; k < argc; k++) {
				pcv = get_component_attribute(pp[i], argv[k]);
				(void) printf("%s\t", (pcv)?(pcv):"NULL");
			}
			(void) printf("\n");
		}
	}
	wsreg_free_component_array(pp);
}
