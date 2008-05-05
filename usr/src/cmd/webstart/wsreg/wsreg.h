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
 * Copyright 2000 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

/*
 * Public header file for clients of the Product Install Registry.
 */

#ifndef	_WSREG_INSTALL_REGISTRY_H
#define	_WSREG_INSTALL_REGISTRY_H


#ifdef __cplusplus
extern "C" {
#endif

#include <sys/types.h>

/*
 * The component type
 */
typedef enum {
	WSREG_PRODUCT = 0,
	WSREG_FEATURE,
	WSREG_COMPONENT
} Wsreg_component_type;

/*
 * The component description
 */
typedef struct Wsreg_component {
	char *id;
	int instance;
	char *version;
	char *unique_name;
	void *display_name;
	void *parent;
	void *children;
	Wsreg_component_type component_type;
	char *location;
	char *uninstaller;
	char *vendor;
	void *required;
	void *dependent;
	void *backward_compatible;
	void *app_data;
} Wsreg_component;

typedef struct Wsreg_query {
	char *id;
	char *unique_name;
	char *version;
	int instance;
	char *location;
} Wsreg_query;

typedef enum {
	WSREG_NOT_INITIALIZED = 1,
	WSREG_INITIALIZING,
	WSREG_INIT_NORMAL,
	WSREG_INIT_NO_CONVERSION
} Wsreg_init_level;

/*
 * Warnings and errors.  Be sure these do not intersect with
 * the /usr/bin/unzip exit codes.
 */
#define	WSREG_SUCCESS 0
#define	WSREG_NO_REG_ACCESS 20
#define	WSREG_CONVERSION_RECOMMENDED 21
#define	WSREG_FILE_NOT_FOUND 22
#define	WSREG_NO_FILE_ACCESS 23
#define	WSREG_UNZIP_ERROR 24
#define	WSREG_CANT_CREATE_TMP_DIR 25
#define	WSREG_UNZIP_NOT_INSTALLED 26
#define	WSREG_BAD_REGISTRY_FILE 2304

/*
 * Exit codes.
 */
#define	WSREG_EXIT_NOT_ENOUGH_MEMORY 2

/*
 * This is the prototype of a progress callback used for registry
 * conversion.
 */
typedef void (*Progress_function)(int progress_percent);

/*
 * Function prototypes
 */
int wsreg_initialize(Wsreg_init_level level, const char *alternate_root);
int wsreg_is_available();
int wsreg_can_access_registry(int access_flag);
char *wsreg_get_alternate_root();
void wsreg_set_alternate_root(const char *alternate_root);
Wsreg_component* wsreg_create_component(const char *compID);
void wsreg_free_component(Wsreg_component *comp);

int wsreg_set_id(Wsreg_component *comp, const char *compID);
char *wsreg_get_id(const Wsreg_component *comp);
int wsreg_set_instance(Wsreg_component *comp, int instance);
int wsreg_get_instance(const Wsreg_component *comp);
int wsreg_set_version(Wsreg_component *comp, const char *version);
char *wsreg_get_version(const Wsreg_component *comp);
int wsreg_set_unique_name(Wsreg_component *comp, const char *unique_name);
char *wsreg_get_unique_name(const Wsreg_component *comp);
int wsreg_add_display_name(Wsreg_component *comp, const char *language,
    const char *display_name);
int wsreg_remove_display_name(Wsreg_component *comp, const char *language);
char *wsreg_get_display_name(const Wsreg_component *comp, const char *language);
char **wsreg_get_display_languages(const Wsreg_component *comp);
int wsreg_set_type(Wsreg_component *comp, Wsreg_component_type type);
Wsreg_component_type wsreg_get_type(const Wsreg_component *comp);
int wsreg_set_location(Wsreg_component *comp, const char *location);
char *wsreg_get_location(const Wsreg_component *comp);
int wsreg_set_uninstaller(Wsreg_component *comp, const char *uninstaller);
char *wsreg_get_uninstaller(const Wsreg_component *comp);
int wsreg_set_vendor(Wsreg_component *comp, const char *vendor);
char *wsreg_get_vendor(const Wsreg_component *comp);

int wsreg_components_equal(const Wsreg_component *comp1,
    const Wsreg_component *comp2);
Wsreg_component *wsreg_clone_component(const Wsreg_component *comp);
int wsreg_add_required_component(Wsreg_component *comp,
    const Wsreg_component *requiredComp);
int wsreg_remove_required_component(Wsreg_component *comp,
				    const Wsreg_component *requiredComp);
Wsreg_component **wsreg_get_required_components(const Wsreg_component *comp);
int wsreg_add_dependent_component(Wsreg_component *comp,
    const Wsreg_component *dependentComp);
int wsreg_remove_dependent_component(Wsreg_component *comp,
    const Wsreg_component *dependentComp);
Wsreg_component **wsreg_get_dependent_components(const Wsreg_component *comp);
Wsreg_component **wsreg_get_child_components(const Wsreg_component *comp);
int wsreg_add_child_component(Wsreg_component *comp,
    const Wsreg_component *childComp);
int wsreg_remove_child_component(Wsreg_component *comp,
    const Wsreg_component *childComp);
int wsreg_add_compatible_version(Wsreg_component *comp, const char *version);
int wsreg_remove_compatible_version(Wsreg_component *comp, const char *version);
char **wsreg_get_compatible_versions(const Wsreg_component *comp);
Wsreg_component* wsreg_get_parent(const Wsreg_component *comp);
void wsreg_set_parent(Wsreg_component *comp,
    const Wsreg_component *parent);
char *wsreg_get_data(const Wsreg_component *comp, const char *key);
int wsreg_set_data(Wsreg_component *comp, const char *key, const char *value);
char **wsreg_get_data_pairs(const Wsreg_component *comp);
Wsreg_component *wsreg_get(const Wsreg_query *query);
int wsreg_register(Wsreg_component *comp);
int wsreg_unregister(const Wsreg_component *comp);

Wsreg_component *wsreg_get_parent_reference(const Wsreg_component *comp);
Wsreg_component **wsreg_get_child_references(const Wsreg_component *comp);
Wsreg_component **wsreg_get_required_references(const Wsreg_component *comp);
Wsreg_component **wsreg_get_dependent_references(const Wsreg_component *comp);

Wsreg_component **wsreg_get_all(void);
Wsreg_component **wsreg_get_sys_pkgs(Progress_function progress_callback);
Wsreg_component **wsreg_get_xall(void);
void wsreg_flag_broken_components(Wsreg_component **comps);
int wsreg_free_component_array(Wsreg_component **complist);
int wsreg_can_convert_registry(const char *filename);
char *wsreg_get_old_registry_name();
int wsreg_convert_registry(const char *filename, int *conversion_count,
    Progress_function progress_callback);
void diag(const char *format, int cnt, ...);

Wsreg_query* wsreg_query_create();
void wsreg_query_free(Wsreg_query *query);
int wsreg_query_set_id(Wsreg_query *query, const char *compID);
char *wsreg_query_get_id(const Wsreg_query *query);
int wsreg_query_set_unique_name(Wsreg_query *query, const char *unique_name);
char *wsreg_query_get_unique_name(const Wsreg_query *query);
int wsreg_query_set_version(Wsreg_query *query, const char *version);
char *wsreg_query_get_version(const Wsreg_query *query);
int wsreg_query_set_instance(Wsreg_query *query, int instance);
int wsreg_query_get_instance(const Wsreg_query *query);
int wsreg_query_set_location(Wsreg_query *query, const char *location);
char *wsreg_query_get_location(const Wsreg_query *query);

void * wsreg_malloc(size_t size);

#ifdef	__cplusplus
}
#endif

#endif /* _WSREG_INSTALL_REGISTRY_H */
