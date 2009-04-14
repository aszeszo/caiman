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

#include <stdio.h>
#include <stdlib.h>
#include <sys/param.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <string.h>
#include <errno.h>
#include <libscf.h>
#include <libaiscf.h>

#include "installadm.h"

static void
usage(void)
{
	printf("Usage: \n" \
	    "\tcreate_pg <pg name> \n" \
	    "\tdelete_pg <pg name> \n" \
	    "\tadd_prop_to_pg <pg name> <prop name> <prop value> \n" \
	    "\tchange_prop <pg name> <prop name> <prop value> \n" \
	    "\tread_props <pg name> \n" \
	    "\tread_property <pg_name> <prop name> \n" \
	    "\tlist_pgs \n");
}

int
create_pg(char *argv[], scfutilhandle_t *handle)
{
	char	*pg_name;

	if ((pg_name = ai_make_pg_name(argv[2])) == NULL) {
		return (1);
	}
	printf("Creating property group %s\n", pg_name);
	ai_create_install_service(handle, pg_name);
	return (0);
}

int
delete_pg(char *argv[], scfutilhandle_t *handle)
{
	char	*pg_name;

	if ((pg_name = ai_make_pg_name(argv[2])) == NULL) {
		return (1);
	}
	printf("Deleting property group %s\n", argv[2]);
	if (ai_delete_install_service(handle, pg_name) != 0) {
		printf("Unable to delete %s\n", argv[2]);
		return (1);
	}
	return (0);
}

int
add_prop_to_pg(char *argv[], scfutilhandle_t *handle)
{
	char	*pg_name;
	char	*prop_name;
	char	*prop_value;

	if ((pg_name = ai_make_pg_name(argv[2])) == NULL) {
		return (1);
	}
	prop_name = argv[3];
	prop_value = argv[4];

	printf("Adding property %s with value %s to property group %s\n",
	    prop_name, prop_value, pg_name);

	if (ai_set_property(handle, pg_name, prop_name, prop_value) !=
	    AI_SUCCESS) {
		return (1);
	}

	return (0);
}

int
change_prop(char *argv[], scfutilhandle_t *handle)
{
	char	*pg_name;
	char	*prop_name;
	char	*prop_value;

	int ret = 0;
	scf_value_t *value;
	scf_transaction_entry_t *entry;

	if ((pg_name = ai_make_pg_name(argv[2])) == NULL) {
		return (1);
	}
	prop_name = argv[3];
	prop_value = argv[4];

	printf("Changing property %s to value %s in property group %s\n",
	    prop_name, prop_value, pg_name);

	if (ai_change_property(handle, pg_name, prop_name, prop_value) !=
	    AI_SUCCESS) {
		return (1);
	}

	return (0);
}

int
read_props(char *argv[], scfutilhandle_t *handle)
{
	char	*pg_name;

	if ((pg_name = ai_make_pg_name(argv[2])) == NULL) {
		return (1);
	}
	printf("Reading properties from property group %s\n", pg_name);

	if (ai_read_all_props_in_pg(handle, pg_name) != AI_SUCCESS) {
		return (1);
	}

	return (0);
}

int
read_property(char *argv[], scfutilhandle_t *handle)
{
	char	*pg_name;
	char	*prop_name;
	char	*property;

	if ((pg_name = ai_make_pg_name(argv[2])) == NULL) {
		return (1);
	}
	prop_name = argv[3];

	printf("Reading property %s from property group %s\n", prop_name,
	    pg_name);

	if ((property = ai_read_property(handle, pg_name, prop_name)) == NULL) {
		return (1);
	}
	printf("%s = %s\n", prop_name, property);

	return (0);
}

int
list_pgs(scfutilhandle_t *handle)
{
	scf_iter_t	*iter = NULL;
	char		*buff = NULL;
	int		ret = 0;

	printf("Listing property groups\n");

	buff = malloc(ai_get_scf_limit(SCF_LIMIT_MAX_NAME_LENGTH));
	if (buff == NULL) {
		printf("Unable to malloc buffer\n");
		return (1);
	}

	iter = scf_iter_create(handle->handle);
	if (iter == NULL) {
		printf("Unable to setup to iterate through property groups\n");
		ret = 1;
		goto out;
	}

	if (ai_get_instance(handle, "default") != AI_SUCCESS) {
		printf("Unable to get default instance\n");
		ret = 1;
		goto out;
	}

	if (scf_iter_instance_pgs(iter, handle->instance) != 0) {
		printf("Unable to get memory to iterate\n");
		ret = 1;
		goto out;
	}

	while (scf_iter_next_pg(iter, handle->pg) > 0) {
		if (scf_pg_get_name(handle->pg, buff,
		    ai_get_scf_limit(SCF_LIMIT_MAX_NAME_LENGTH)) >= 0) {
			if (strncmp("AI", buff, 2) == 0) {
				printf("%s\n", &buff[2]);
			}
		}
	}
out:
	if (buff != NULL)
		free(buff);
	if (iter != NULL)
		scf_iter_destroy(iter);

	return (ret);
}

int
main(int argc, char *argv[])
{
	char *subcommand;
	scfutilhandle_t	*handle;

	handle = ai_scf_init();
	if (handle == NULL) {
		printf("ai_scf_init failed\n");
		return (1);
	}
	subcommand = argv[1];
	if (strcmp(subcommand, "create_pg") == 0) {
		if (create_pg(argv, handle) != 0) {
			printf("create_pg failed\n");
			return (1);
		}
	} else if (strcmp(subcommand, "delete_pg") == 0) {
		if (delete_pg(argv, handle) != 0) {
			printf("delete_pg failed\n");
			return (1);
		}
	} else if (strcmp(subcommand, "add_prop_to_pg") == 0) {
		if (add_prop_to_pg(argv, handle) != 0) {
			printf("add_prop_to_pg failed\n");
			return (1);
		}
	} else if (strcmp(subcommand, "change_prop") == 0) {
		if (change_prop(argv, handle) != 0) {
			printf("change_prop failed\n");
			return (1);
		}
	} else if (strcmp(subcommand, "read_props") == 0) {
		if (read_props(argv, handle) != 0) {
			printf("read_props failed\n");
			return (1);
		}
	} else if (strcmp(subcommand, "read_property") == 0) {
		if (read_property(argv, handle) != 0) {
			printf("read_property failed\n");
			return (1);
		}
	} else if (strcmp(subcommand, "list_pgs") == 0) {
		if (list_pgs(handle) != 0) {
			printf("list_pgs failed\n");
			return (1);
		}
	} else {
		usage();
		return (1);
	}

	return (0);
}
