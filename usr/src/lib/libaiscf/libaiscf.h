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

#ifndef	_LIBAISCF_H
#define	_LIBAISCF_H
#include <libscf.h>

typedef struct scfutilhandle {
	scf_handle_t		*handle;
	int			scf_state;
	scf_service_t		*service;
	scf_scope_t		*scope;
	scf_transaction_t	*trans;
	scf_transaction_entry_t	*entry;
	scf_propertygroup_t	*pg;
	scf_instance_t		*instance;
} scfutilhandle_t;


#define	AI_DEFAULT_SERVER_SVC_NAME	"system/install/server"

/*
 * libaiscf error codes
 */
typedef enum ai_errno {
	AI_SUCCESS = 0,
	AI_NO_SUCH_INSTANCE = 6000,	/* instance doesn't exist */
	AI_NO_SUCH_PG,			/* property group doesn't exist */
	AI_CONFIG_ERR,			/* Server Configuration error */
	AI_SYSTEM_ERR,			/* SMF System Error */
	AI_NO_PERMISSION,		/* Permission Denied */
	AI_INVAL_ARG,			/* Invalid argument */
	AI_TRANS_ERR,			/* Transaction failed */
	AI_NO_MEM,			/* Memory Allocation failure */
	AI_PG_CREAT_ERR,		/* Failed to create PG */
	AI_PG_DELETE_ERR,		/* Failed to delete PG */
	AI_PG_ITER_ERR,			/* Property iteration failure */
	AI_PG_EXISTS_ERR,		/* property group already exists */
	AI_NO_SUCH_PROP			/* property doesn't exist */
} ai_errno_t;

/*
 * Property group/Property structures
 */
typedef struct ai_pg_list {
	struct ai_pg_list	*next;
	char			*pg_name;
} ai_pg_list_t;

typedef struct ai_prop_list {
	struct ai_prop_list	*next;
	char			*name;
	char			*valstr;
} ai_prop_list_t;

/*
 * Public function definitions
 */
scfutilhandle_t *ai_scf_init();
void ai_scf_fini(scfutilhandle_t *);
ai_errno_t ai_create_pg(scfutilhandle_t *, char *);
ai_errno_t ai_get_instance(scfutilhandle_t *, char *);
ai_errno_t ai_get_pg(scfutilhandle_t *, char *);
ai_errno_t ai_delete_pg(scfutilhandle_t *, char *);
ai_errno_t ai_delete_property(scfutilhandle_t *, char *, char *);
ai_errno_t ai_start_transaction(scfutilhandle_t *, char *);
ai_errno_t ai_end_transaction(scfutilhandle_t *);
ai_errno_t ai_transaction_set_property(scfutilhandle_t *, char *, char *);
void ai_abort_transaction(scfutilhandle_t *);
char *ai_make_pg_name(char *);
ai_errno_t ai_set_property(scfutilhandle_t *, char *, char *, char *);
ai_errno_t ai_read_property(scfutilhandle_t *, char *, char *, char **);
ai_errno_t ai_read_all_props_in_pg(scfutilhandle_t *, char *,
    ai_prop_list_t **);
void ai_free_prop_list(ai_prop_list_t *);
void ai_free_pg_list(ai_pg_list_t *);
int ai_list_pgs(scfutilhandle_t *);
ai_errno_t ai_get_pgs(scfutilhandle_t *, ai_pg_list_t **);
char *ai_strerror(int);

#endif /* _LIBAISCF_H */
