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

#ifndef _LIBERRSVC_H
#define	_LIBERRSVC_H

#include <string.h>
#include <sys/types.h>

#include "liberrsvc_defs.h"

typedef void *err_info_t;

typedef struct err_info_list {
	err_info_t *ei_err_info;
	struct err_info_list *ei_next;
} err_info_list_t;

/*
 * Public interface functions
 */
err_info_t *es_create_err_info(char *, int);
boolean_t es_set_err_data_int(err_info_t *, int, int);
boolean_t es_set_err_data_str(err_info_t *, int, char *, ...);
void es_free_err_info_list(err_info_list_t *);
void es_free_errors();
err_info_list_t *es_get_errors_by_type(int, boolean_t *);
err_info_list_t *es_get_errors_by_modid(char *);
err_info_list_t *es_get_all_errors();
int es_get_err_type(err_info_t *);
char *es_get_err_mod_id(err_info_t *);
boolean_t es_get_err_data_int_by_type(err_info_t *, int, int *);
boolean_t es_get_err_data_str_by_type(err_info_t *, int, char **);
int es_get_failure_reason_int(void);
const char *es_get_failure_reason_str(void);

#endif	/* _LIBERRSVC_H */
