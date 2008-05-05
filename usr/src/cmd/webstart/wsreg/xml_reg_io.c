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
 * Copyright 2003 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include <sys/param.h>
#include "wsreg_private.h"
#include "wsreg.h"
#include "boolean.h"
#include "list.h"
#include "xml_reg_io.h"
#include "reg_comp.h"
#include "file_token.h"
#include "file_util.h"
#include "string_util.h"

static char *_alternate_root = NULL;
static Reg_comp *_comp_obj = NULL;
static File_token *saved_token = NULL;
static Wsreg_component **saved_components = NULL;

static void
set_file_names(Xml_reg_io *);
static _Wsreg_instance *
create_instance(char *, int, char *);


/*
 * This structure is used to associate xml reg io private
 * data to its associated object.
 */
struct _Xml_reg_io_private
{
	Xml_file_io *xml_file;
	Xml_file_mode mode;
	mode_t permissions;
	Wsreg_component **components;
	char *version;
} _Xml_reg_io_private;

#define	REGISTRY_VERSION	"0.8"

/*
 * The following defines make it easy to refer to the
 * xml tags in a switch statement.
 */
#define	PRODUCTREGISTRY	0
#define	VERSION		1
#define	INSTALLED	2
#define	COMPONENTS	3
#define	NAMEMAP		4
#define	COMPID		5
#define	COMPVERSION	6
#define	UNIQUENAME	7
#define	DISPLAYNAME	8
#define	COMPINSTANCE	9
#define	PARENT		10
#define	COMPTYPE	11
#define	LOCATION	12
#define	UNINSTALLER	13
#define	COMPATIBLE	14
#define	DEPENDENT	15
#define	REQUIRED	16
#define	DATA		17
#define	INSTANCE	18
#define	COMPREF		19
#define	KEY		20
#define	VALUE		21
#define	NAME		22
#define	ID		23
#define	VENDOR		24
#define	CHILDREN	25
#define	LANGUAGE	26
#define	LOCALIZEDNAME	27


static char *_tagtab[] =
{
	"productregistry",
	"version",
	"installed",
	"components",
	"namemap",
	"compid",
	"compversion",
	"uniquename",
	"displayname",
	"compinstance",
	"parent",
	"comptype",
	"location",
	"uninstaller",
	"compatible",
	"dependent",
	"required",
	"data",
	"instance",
	"compref",
	"key",
	"value",
	"name",
	"id",
	"vendor",
	"children",
	"language",
	"localizedname",
	NULL
};

static String_map *tag_map = NULL;


/*
 * Prototypes
 */
static Wsreg_component **
read_components(Xml_reg_io *xr);
static void
write_components(Xml_reg_io *xr);

/*
 * Frees the specified object.
 */
static void
xrio_free(Xml_reg_io *xr)
{
	if (xr->pdata->xml_file != NULL)
		xr->pdata->xml_file->free(xr->pdata->xml_file);

	/*
	 * Free the component array.
	 */
	if (xr->pdata->components != NULL) {
		(void)
		    _comp_obj->free_array(
			    xr->pdata->components);
		xr->pdata->components = NULL;
	}

	if (xr->pdata->version != NULL)
		free(xr->pdata->version);

	free(xr->pdata);
	free(xr);
}

/*
 * Opens the xml file.
 */
static void
xrio_open(Xml_reg_io *xr, Xml_file_mode mode)
{
	Xml_file_io *xf = xr->pdata->xml_file;
	xr->pdata->mode = mode;

	xf->open(xf, mode, xr->pdata->permissions);
	xr->read(xr);
}

/*
 * Closes the xml file.
 */
static void
xrio_close(Xml_reg_io *xr)
{
	if (xr->pdata->mode == READWRITE) {
		/*
		 * The file was opened in READ/WRITE
		 * mode.  Write the file before closing.
		 */
		Xml_file_io *xf = xr->pdata->xml_file;
		xr->write(xr);
		xr->pdata->xml_file->close(xr->pdata->xml_file);
		if (saved_token != NULL)
			saved_token->free(saved_token);
		saved_token = _wsreg_ftoken_create(xf->get_file_name(xf));

	} else {
		xr->pdata->xml_file->close(xr->pdata->xml_file);
	}

	/*
	 * Free the component array.
	 */
	if (xr->pdata->components != NULL) {
		(void) _comp_obj->free_array(xr->pdata->components);
		xr->pdata->components = NULL;
	}
}

/*
 * Sets the specified alternate root.
 */
static void
xrio_set_alternate_root(Xml_reg_io *xr, const char *alternate_root)
{
	String_util *sutil = _wsreg_strutil_initialize();
	if (_alternate_root != NULL) {
		free(_alternate_root);
		_alternate_root = NULL;
	}
	if (alternate_root != NULL) {
		/*
		 * Remove the trailing "/"
		 */
		int len = strlen(alternate_root);
		if (len > 0 &&
		    alternate_root[len - 1] == '/') {
			len--;
		}
		_alternate_root =  sutil->clone(alternate_root);
		_alternate_root[len] = '\0';
	} else {
		_alternate_root = sutil->clone("");
	}

	set_file_names(xr);
}

/*
 * Sets the specified permissions into the specified
 * xml reg io object.
 */
static void
xrio_set_permissions(Xml_reg_io *xr, mode_t permissions)
{
	xr->pdata->permissions = permissions;
}

/*
 * Returns the permissions associated with the specified
 * xml reg io object.
 */
static mode_t
xrio_get_permissions(Xml_reg_io *xr)
{
	return (xr->pdata->permissions);
}

/*
 * Sets the specified components.
 */
static void
xrio_set_components(Xml_reg_io *xr, Wsreg_component **comps)
{
	if (xr->pdata->components != NULL) {
		/*
		 * Don't free the array; the old components
		 * probably appear in the new array.
		 */
		free(xr->pdata->components);
	}
	xr->pdata->components = comps;
}

/*
 * Returns the components from the specified object.
 */
static Wsreg_component **
xrio_get_components(Xml_reg_io *xr)
{
	return (xr->pdata->components);
}

/*
 * Reads the components from the registry.
 */
static void
xrio_read(Xml_reg_io *xr)
{
	Xml_tag *tag = NULL;
	Xml_file_io *xf = xr->pdata->xml_file;
	File_token *ftoken = _wsreg_ftoken_create(xf->get_file_name(xf));
	String_util *sutil = _wsreg_strutil_initialize();

	if (saved_token != NULL &&
	    saved_components != NULL &&
	    saved_token->equals(saved_token, ftoken)) {
		/*
		 * We optimize by not performing the read when
		 * the data file has not changed.
		 */
		ftoken->free(ftoken);
		if (xr->pdata->components != NULL)
			(void) _comp_obj->free_array(xr->pdata->components);
		xr->pdata->components =
		    _comp_obj->clone_array(saved_components);
		return;
	}
	ftoken->free(ftoken);

	if (xr->pdata->components != NULL) {
		(void) _comp_obj->free_array(xr->pdata->components);
	}

	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			if (xr->get_components(xr) == NULL) {
				Wsreg_component **comps =
				    (Wsreg_component **)
				    wsreg_malloc(sizeof (Wsreg_component*));
				comps[0] = NULL;
				xr->set_components(xr, comps);
			}
			return;
		}
		switch (tag->get_tag(tag)) {
		case PRODUCTREGISTRY:
			if (tag->is_end_tag(tag)) {
				tag->free(tag);
				if (xr->get_components(xr) == NULL) {
					Wsreg_component **comps =
					    (Wsreg_component**)
					    wsreg_malloc(
						    sizeof (Wsreg_component*));
					comps[0] = NULL;
					xr->set_components(xr, comps);
				}
				saved_token =
				    _wsreg_ftoken_create(xf->get_file_name(xf));
				if (saved_components != NULL)
					_comp_obj->free_array(saved_components);
				saved_components =
				    _comp_obj->clone_array(
					    xr->pdata->components);
				return;
			}
			break;

		case VERSION:
			if (!tag->is_end_tag(tag)) {
				xr->pdata->version =
				    sutil->clone(tag->get_value_string(tag));
				if (strcmp(tag->get_value_string(tag),
				    REGISTRY_VERSION) > 0) {
					diag("The registry file "
					    "version is more recent than this "
					    "library can handle.\n", 0);
					tag->free(tag);
					return;
				}
			}
			break;

		case COMPONENTS:
			if (!tag->is_end_tag(tag)) {
				/*
				 * Read the installed components.
				 */
				xr->set_components(xr, read_components(xr));
			}
			break;

		}
		tag->free(tag);
	}
}

/*
 * Writes the components into the registry.
 */
static void
xrio_write(Xml_reg_io *xr)
{
	Xml_tag *tag = _wsreg_xtag_create();
	Xml_file_io *xf = xr->pdata->xml_file;

	tag->set_tag(tag, tag_map, "productregistry");
	xf->write_tag(xf, tag);

	tag->set_tag(tag, tag_map, "version");
	tag->set_value_string(tag, REGISTRY_VERSION);
	xf->write_tag(xf, tag);
	xf->write_close_tag(xf, tag);

	tag->set_tag(tag, tag_map, "components");
	tag->set_value_string(tag, NULL);
	xf->write_tag(xf, tag);

	/*
	 * Write the component info here.
	 */
	write_components(xr);

	xf->write_close_tag(xf, tag);

	tag->set_tag(tag, tag_map, "productregistry");
	xf->write_close_tag(xf, tag);

	tag->free(tag);

	if (saved_components != NULL)
		(void) _comp_obj->free_array(saved_components);
	saved_components = _comp_obj->clone_array(xr->pdata->components);
}

/*
 * Returns true if the registry can be read; false
 * otherwise.
 */
static Boolean
xrio_can_read_registry(Xml_reg_io *xr)
{
	Boolean result = FALSE;
	if (xr != NULL) {
		Xml_file_io *xf = xr->pdata->xml_file;
		char *registry_file = xf->get_file_name(xf);
		File_util *futil = _wsreg_fileutil_initialize();

		/*
		 * If the file does not exist, see if the registry
		 * directory can be read.
		 */
		if (!futil->exists(registry_file)) {
			char *parent = futil->get_parent(registry_file);
			if (parent != NULL) {
				result = futil->can_read(parent);
				free(parent);
			}
		} else {
			result = futil->can_read(registry_file);
		}
	}
	return (result);
}

/*
 * Returns true if the registry can be modified;
 * false otherwise.
 */
static Boolean
xrio_can_modify_registry(Xml_reg_io *xr)
{
	Boolean result = FALSE;
	if (xr != NULL) {
		Xml_file_io *xf = xr->pdata->xml_file;
		char *registry_file = xf->get_file_name(xf);
		char *registry_backup = xf->get_backup_file_name(xf);
		char *registry_new = xf->get_new_file_name(xf);
		File_util *futil = _wsreg_fileutil_initialize();
		if (futil->exists(registry_file)) {
			result = futil->can_write(registry_file);
		} else {
			char *parent = futil->get_parent(registry_file);
			if (parent != NULL) {
				result = futil->can_read(parent);
				free(parent);
			}
		}

		if (futil->exists(registry_backup)) {
			result &= futil->can_write(registry_backup);
		} else {
			char *parent = futil->get_parent(registry_backup);
			if (parent != NULL) {
				result &= futil->can_read(parent);
				free(parent);
			}
		}
		if (futil->exists(registry_new)) {
			result &= futil->can_write(registry_new);
		} else {
			char *parent = futil->get_parent(registry_new);
			if (parent != NULL) {
				result &= futil->can_read(parent);
				free(parent);
			}
		}
	}
	return (result);
}

/*
 * Creates an xml reg io object.
 */
Xml_reg_io *
_wsreg_xregio_create()
{
	Xml_reg_io *xr = (Xml_reg_io*)wsreg_malloc(sizeof (Xml_reg_io));
	struct _Xml_reg_io_private *p = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	if (_comp_obj == NULL)
		_comp_obj = _wsreg_comp_initialize();

	/*
	 * Load the method set.
	 */
	xr->free = xrio_free;
	xr->open = xrio_open;
	xr->close = xrio_close;
	xr->set_alternate_root = xrio_set_alternate_root;
	xr->set_permissions = xrio_set_permissions;
	xr->get_permissions = xrio_get_permissions;
	xr->read = xrio_read;
	xr->write = xrio_write;
	xr->set_components = xrio_set_components;
	xr->get_components = xrio_get_components;
	xr->can_read_registry = xrio_can_read_registry;
	xr->can_modify_registry = xrio_can_modify_registry;

	/*
	 * Initialize the alternate root
	 */
	if (_alternate_root == NULL)
		_alternate_root = sutil->clone("");

	/*
	 * Initialize the tag map
	 */
	if (tag_map == NULL)
		tag_map = _wsreg_stringmap_create(_tagtab);

	/*
	 * Initialize the private data.
	 */
	p = (struct _Xml_reg_io_private *)
	    wsreg_malloc(sizeof (struct _Xml_reg_io_private));
	p->xml_file = _wsreg_xfio_create(tag_map);
	p->mode = READONLY;
	p->permissions = S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH;
	p->components = NULL;
	p->version = NULL;

	xr->pdata = p;
	set_file_names(xr);
	return (xr);
}

/*
 * Sets the registry filenames into the xml file context.
 */
static void
set_file_names(Xml_reg_io *xr)
{
	char current_file_name[MAXPATHLEN];
	char backup_file_name[MAXPATHLEN];
	char new_file_name[MAXPATHLEN];

	(void) sprintf(current_file_name, "%s%s/%s",
	    _alternate_root,
	    REGISTRY_LOCATION,
	    REGISTRY_FILE);
	(void) sprintf(backup_file_name, "%s%s/%s",
	    _alternate_root,
	    REGISTRY_LOCATION,
	    REGISTRY_ORIGINAL);
	(void) sprintf(new_file_name, "%s%s/%s",
	    _alternate_root,
	    REGISTRY_LOCATION,
	    REGISTRY_UPDATE);
	xr->pdata->xml_file->set_file_names(xr->pdata->xml_file,
	    current_file_name,
	    backup_file_name,
	    new_file_name);
}

/*
 * Resizes the specified component array.
 */
static Wsreg_component **
resize_component_array(Wsreg_component **comparray, int newsize)
{
	int currentsize = _comp_obj->array_size(comparray);
	int i = 0;

	comparray = (Wsreg_component**)realloc(comparray,
	    sizeof (Wsreg_component*)  *newsize);
	/*
	 * Fill in the remaining elements with NULL.
	 */
	for (i = currentsize; i < newsize; i++) {
		comparray[i] = NULL;
	}

	return (comparray);
}

/*
 * Reads the display name from the xml file.
 */
static void
read_display_name(Xml_reg_io *xr, Wsreg_component *comp)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;
	char *language = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return;
		}
		switch (tag->get_tag(tag)) {
		case DISPLAYNAME:
			if (tag->is_end_tag(tag)) {
				tag->free(tag);
				if (language != NULL)
					free(language);
				return;
			}
			break;

		case LANGUAGE:
			if (!tag->is_end_tag(tag)) {
				if (language != NULL)
					free(language);
				language = sutil->clone(
					tag->get_value_string(tag));
			}
			break;

		case LOCALIZEDNAME:
			if (!tag->is_end_tag(tag)) {
				if (language != NULL) {
					char *name = tag->get_value_string(tag);

					/*
					 * The following line of code will be
					 * used to add the new language/name
					 * pair to the component.  For now,
					 * we will simply set the "en" variant
					 * into the displayname string.
					 */
					(void) _comp_obj->add_display_name(
						comp, language, name);
					/*
					 * Don't forget to free the language
					 * string.
					 */
					free(language); language = NULL;
				}
			}
			break;

		}
		tag->free(tag);
	}
}

/*
 * Reads a component reference from the registry
 * file.
 */
static _Wsreg_instance *
read_instance(Xml_reg_io *xr, char *id, int instance)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;
	char *version = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return (NULL);
		}
		switch (tag->get_tag(tag)) {
		case INSTANCE:
			if (tag->is_end_tag(tag)) {
				_Wsreg_instance *inst =
				    create_instance(id, instance,
					version);
				tag->free(tag);
				if (version != NULL)
					free(version);
				return (inst);
			}
			break;

		case VERSION:
			if (!tag->is_end_tag(tag)) {
				if (version != NULL) {
					free(version);
				}
				version = tag->get_value_string(tag);
				if (version != NULL) {
					version = sutil->clone(version);
				}
			}
			break;

		}
		tag->free(tag);
	}
}

/*
 * Reads a component reference from the xml file.
 */
static _Wsreg_instance *
read_component_reference(Xml_reg_io *xr, int parenttag, char *id)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;
	_Wsreg_instance *compinstance = NULL;

	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return (compinstance);
		}

		if (tag->is_end_tag(tag) && tag->get_tag(tag) == parenttag) {
			tag->free(tag);
			return (compinstance);
		}

		switch (tag->get_tag(tag)) {
		case INSTANCE:
			if (!tag->is_end_tag(tag)) {
				int parentinstance = atoi(
					tag->get_value_string(tag));
				compinstance = read_instance(xr, id,
				    parentinstance);
			}
			break;

		}
		tag->free(tag);
	}
}

/*
 * Reads a list of component references from the registry
 * file.
 */
static List *
read_component_reference_list(Xml_reg_io *xr, int parenttag)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;

	List *referenceList = NULL;

	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return (referenceList);
		}

		if (tag->get_tag(tag) == parenttag) {
			tag->free(tag);
			return (referenceList);
		}

		switch (tag->get_tag(tag)) {
		case COMPREF:
			if (!tag->is_end_tag(tag)) {
				_Wsreg_instance *compinstance = NULL;
				compinstance = read_component_reference(xr,
				    COMPREF, tag->get_value_string(tag));
				if (compinstance != NULL) {
					if (referenceList == NULL) {
						/*
						 * Create a new list to hold the
						 * component references.
						 */
						referenceList =
						    _wsreg_list_create();
					}
					referenceList->add_element(
						referenceList,
						    compinstance);
				}
			}
			break;

		}
		tag->free(tag);
	}
}

/*
 * Reads the compatible versions from the xml file.
 */
static void
read_component_compatibility(Xml_reg_io *xr, Wsreg_component *comp)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;

	Boolean done = FALSE;
	while (!done) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return;
		}
		switch (tag->get_tag(tag)) {
		case COMPATIBLE:
			if (tag->is_end_tag(tag)) {
				done = TRUE;
			}
			break;

		case VERSION:
			if (!tag->is_end_tag(tag)) {
				(void)
				    _comp_obj->add_compatible_version(comp,
					tag->get_value_string(tag));
			}
			break;
		}
		tag->free(tag);
	}
}

/*
 * Reads a value from the registry.
 */
static char *
read_value(Xml_reg_io *xr)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;
	char *returnvalue = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return (returnvalue);
		}
		switch (tag->get_tag(tag)) {
		case VALUE:
			if (tag->is_end_tag(tag)) {
				tag->free(tag);
				return (returnvalue);
			} else {
				returnvalue = sutil->clone(
					tag->get_value_string(tag));
			}
			break;

		}
		tag->free(tag);
	}
}


/*
 * Reads a key/value pair from the registry file.
 */
static void
read_data(Xml_reg_io *xr, Wsreg_component *comp)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;
	String_util *sutil = _wsreg_strutil_initialize();

	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return;
		}
		switch (tag->get_tag(tag)) {
		case DATA:
			if (tag->is_end_tag(tag)) {
				tag->free(tag);
				return;
			}
			break;

		case KEY:
			if (!tag->is_end_tag(tag)) {
				char *key = sutil->clone(
					tag->get_value_string(tag));
				char *value = read_value(xr);
				(void) _comp_obj->set_data(comp, key, value);
				free(key);
				free(value);
			}
			break;

		}
		tag->free(tag);
	}
}

/*
 * Reads a component instance from the registry file.
 */
static Wsreg_component*
read_component_instance(Xml_reg_io *xr, const Wsreg_component *template,
    int instance)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;
	Wsreg_component *comp = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	/*
	 * Copy the template.
	 */
	comp = _comp_obj->clone(template);

	wsreg_set_instance(comp, instance);
	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return (comp);
		}
		switch (tag->get_tag(tag)) {
		case COMPINSTANCE:
			if (tag->is_end_tag(tag)) {
				tag->free(tag);
				return (comp);
			}
			break;

		case PARENT:
			if (!tag->is_end_tag(tag)) {
				comp->parent =  read_component_reference(xr,
				    PARENT, tag->get_value_string(tag));
			}
			break;

		case CHILDREN:
			if (!tag->is_end_tag(tag)) {
				comp->children =
				    read_component_reference_list(xr, CHILDREN);
			}
			break;


		case COMPTYPE:
			if (!tag->is_end_tag(tag)) {
				int type = WSREG_COMPONENT;
				if (strcmp(tag->get_value_string(tag),
				    "PRODUCT") == 0) {
					type = WSREG_PRODUCT;
				}
				if (strcmp(tag->get_value_string(tag),
				    "FEATURE") == 0) {
					type = WSREG_FEATURE;
				}
				comp->component_type = type;
			}
			break;

		case LOCATION:
			if (!tag->is_end_tag(tag)) {
				comp->location = tag->get_value_string(tag);
				if (comp->location != NULL) {
					comp->location =
					    sutil->clone(comp->location);
				}
			}
			break;

		case UNINSTALLER:
			if (!tag->is_end_tag(tag)) {
				comp->uninstaller =
				    sutil->clone(tag->get_value_string(tag));
			}
			break;

		case COMPATIBLE:
			if (!tag->is_end_tag(tag)) {
				read_component_compatibility(xr, comp);
			}
			break;
		case DEPENDENT:
			if (!tag->is_end_tag(tag)) {
				comp->dependent =
				    read_component_reference_list(xr,
					DEPENDENT);
			}
			break;

		case REQUIRED:
			if (!tag->is_end_tag(tag)) {
				comp->required =
				    read_component_reference_list(xr, REQUIRED);
			}
			break;

		case DATA:
			if (!tag->is_end_tag(tag)) {
				read_data(xr, comp);
			}
			break;

		}
		tag->free(tag);
	}
}

/*
 * Reads the component's version from the registry file.
 */
static Wsreg_component **
read_component_version(Xml_reg_io *xr,
    Wsreg_component *template, char *version)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;
	int arraysize = 5;
	String_util *sutil = _wsreg_strutil_initialize();
	Wsreg_component *comp = NULL;
	Wsreg_component **componentversions =
	    (Wsreg_component **)wsreg_malloc(sizeof (Wsreg_component *)  *
		arraysize);
	int versioncount = 0;

	(void) memset(componentversions, 0, sizeof (Wsreg_component*) *
	    arraysize);

	/*
	 * Copy the template.
	 */
	comp = _comp_obj->create();
	_comp_obj->set_id(comp, template->id);
	_comp_obj->set_version(comp, version);

	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return (componentversions);
		}
		switch (tag->get_tag(tag)) {
		case UNIQUENAME:
			if (!tag->is_end_tag(tag)) {
				comp->unique_name =
				    sutil->clone(tag->get_value_string(tag));
			}
			break;
		case DISPLAYNAME:
			if (!tag->is_end_tag(tag)) {
				read_display_name(xr, comp);
			}
			break;
		case VENDOR:
			if (!tag->is_end_tag(tag)) {
				comp->vendor =
				    sutil->clone(tag->get_value_string(tag));
			}
			break;
		case COMPINSTANCE:
			if (!tag->is_end_tag(tag)) {
				int i = atoi(tag->get_value_string(tag));
				Wsreg_component *compinstance = NULL;
				compinstance = read_component_instance(xr,
				    comp, i);
				if (compinstance != NULL) {
					/*
					 * Add this component to the list of
					 * components returned from this
					 * function.
					 */
					if (versioncount + 1 >= arraysize) {
						componentversions =
						    resize_component_array(
							    componentversions,
								arraysize  *2);
						arraysize = arraysize  *2;
					}

					/*
					 * Add the new instance to the array.
					 */
					componentversions[versioncount++] =
					    compinstance;
				}
			}
			break;
		case COMPVERSION:
			if (tag->is_end_tag(tag)) {
				/*
				 * Done.  Simply return the list of components.
				 */
				tag->free(tag);
				_comp_obj->free(comp);
				return (componentversions);
			}
			break;

		}
		tag->free(tag);
	}
}


/*
 * Reads all components from the component version section
 * of the registry file.
 */
static Wsreg_component **
read_component(Xml_reg_io *xr, const char *id)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;
	int componentcount = 0;
	Wsreg_component *newcomp = _comp_obj->create();
	Wsreg_component **components = NULL;

	_comp_obj->set_id(newcomp, id);

	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return (components);
		}
		switch (tag->get_tag(tag)) {
		case COMPVERSION:
			if (!tag->is_end_tag(tag)) {
				Wsreg_component **comps = NULL;
				/*
				 * This is the beginning of a new component
				 * version.
				 */
				comps = read_component_version(xr, newcomp,
				    tag->get_value_string(tag));
				if (components == NULL) {
					components = comps;
					componentcount =
					    _comp_obj->array_size(components);
				} else {
					/*
					 * Add the new components to the
					 * current component array.
					 */
					int count =
					    _comp_obj->array_size(comps);
					int i;
					components =
					    resize_component_array(components,
						componentcount + count + 1);

					for (i = 0; i < count; i++) {
						components[componentcount++] =
						    comps[i];
					}

					/*
					 * Don't forget to free the now-unused
					 * array.  The elements
					 * must not be freed.
					 */
					free(comps);
				}
			}
			break;

		case COMPID:
			if (tag->is_end_tag(tag)) {
				tag->free(tag);
				_comp_obj->free(newcomp);
				return (components);
			}
			break;
		}
		tag->free(tag);
	}
}

/*
 * Reads all components from the registry.
 */
static Wsreg_component **
read_components(Xml_reg_io *xr)
{
	Xml_tag *tag;
	Xml_file_io *xf = xr->pdata->xml_file;
	unsigned int componentcount = 0;
	Wsreg_component **components = 0;

	for (; ; ) {
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			return (components);
		}
		switch (tag->get_tag(tag)) {
		case COMPID:
			if (tag->is_end_tag(tag)) {
				/*
				 * This is the end of the current component.
				 */
				/*EMPTY*/
			} else {
				/*
				 * This is the beginning of a new component.
				 */
				Wsreg_component **newcomps =
				    read_component(xr,
					tag->get_value_string(tag));
				if (components == NULL) {
					components = newcomps;
					componentcount =
					    _comp_obj->array_size(components);
				} else {
					/*
					 * The component array must be resized
					 * so the new components can be added.
					 */
					int count =
					    _comp_obj->array_size(newcomps);
					int i;
					components =
					    resize_component_array(components,
						componentcount + count + 1);

					for (i = 0; i < count; i++) {
						components[componentcount++] =
						    newcomps[i];
					}

					/*
					 * Don't forget to free the now-unused
					 * array.  The elements must not be
					 * freed.
					 */
					free(newcomps);
				}
			}
			break;

		case COMPONENTS:
			if (tag->is_end_tag(tag)) {
				tag->free(tag);
				return (components);
			}
			break;
		}
		tag->free(tag);
	}
}

/*
 * Writes a component instance into the registry file.
 */
static int
write_instance(Xml_reg_io *xr, const char *parenttag, _Wsreg_instance *instance)
{
	Xml_tag *tag = _wsreg_xtag_create();
	Xml_file_io *xf = xr->pdata->xml_file;

	char instancestring[10];

	tag->set_tag(tag, tag_map, parenttag);
	tag->set_value_string(tag, instance->id);
	xf->write_tag(xf, tag);

	(void) sprintf(instancestring, "%d", instance->instance);
	tag->set_tag(tag, tag_map, "instance");
	tag->set_value_string(tag, instancestring);
	xf->write_tag(xf, tag);

	tag->set_tag(tag, tag_map, "version");
	tag->set_value_string(tag, instance->version);
	xf->write_tag(xf, tag);
	xf->write_close_tag(xf, tag);

	tag->set_tag(tag, tag_map, "instance");
	tag->set_value_string(tag, NULL);
	xf->write_close_tag(xf, tag);

	tag->set_tag(tag, tag_map, parenttag);
	xf->write_close_tag(xf, tag);

	tag->free(tag);
	return (1);
}

/*
 * Writes the specified component references into the registry
 * file.
 */
static int
write_component_references(Xml_reg_io *xr,
    const char *tagString,
    List *referenceList)
{
	Xml_tag *tag = _wsreg_xtag_create();
	Xml_file_io *xf = xr->pdata->xml_file;
	if (tagString != NULL &&
	    referenceList->size(referenceList) > 0) {
		tag->set_tag(tag, tag_map, tagString);
		tag->set_value_string(tag, NULL);
		xf->write_tag(xf, tag);

		referenceList->reset_iterator(referenceList);
		while (referenceList->has_more_elements(referenceList)) {
			_Wsreg_instance *compReference =
			    (_Wsreg_instance*)
			    referenceList->next_element(referenceList);
			(void) write_instance(xr, "compref",
			    compReference);
		}

		xf->write_close_tag(xf, tag);
	}
	tag->free(tag);
	return (1);
}

/*
 * Writes the specified list of versions into the registry
 * file.
 */
static int
write_versions(Xml_reg_io *xr,
    const char *tagString,
    List *versionList)
{
	Xml_tag *tag = _wsreg_xtag_create();
	Xml_file_io *xf = xr->pdata->xml_file;

	if (tagString != NULL &&
	    versionList->size(versionList) > 0) {
		tag->set_tag(tag, tag_map, tagString);
		xf->write_tag(xf, tag);

		versionList->reset_iterator(versionList);
		while (versionList->has_more_elements(versionList)) {
			char *version =
			    (char *)versionList->next_element(versionList);
			if (version != NULL) {
				tag->set_tag(tag, tag_map, "version");
				tag->set_value_string(tag, version);
				xf->write_tag(xf, tag);
				xf->write_close_tag(xf, tag);
			}
		}
		tag->set_tag(tag, tag_map, tagString);
		tag->set_value_string(tag, NULL);
		xf->write_close_tag(xf, tag);
	}
	tag->free(tag);
	return (1);
}

/*
 * Writes the specified key/value pair into the registry
 * file.
 */
static int
write_paired_data(Xml_reg_io *xr,
    const char *tagString,
    const char *keyString,
    const char *valueString,
    List *dataList)
{
	Xml_tag *tag = _wsreg_xtag_create();
	Xml_file_io *xf = xr->pdata->xml_file;

	if (tagString != NULL &&
	    dataList->size(dataList) > 0) {
		tag->set_tag(tag, tag_map, tagString);
		xf->write_tag(xf, tag);

		dataList->reset_iterator(dataList);
		while (dataList->has_more_elements(dataList)) {
			_Wsreg_data *data = dataList->next_element(dataList);
			if (data->key != NULL &&
			    data->value != NULL) {
				tag->set_tag(tag, tag_map, keyString);
				tag->set_value_string(tag, data->key);
				xf->write_tag(xf, tag);

				tag->set_tag(tag, tag_map, valueString);
				tag->set_value_string(tag, data->value);
				xf->write_tag(xf, tag);
				xf->write_close_tag(xf, tag);

				tag->set_tag(tag, tag_map, keyString);
				tag->set_value_string(tag, NULL);
				xf->write_close_tag(xf, tag);
			}
		}
		tag->set_tag(tag, tag_map, tagString);
		tag->set_value_string(tag, NULL);
		xf->write_close_tag(xf, tag);
	}

	tag->free(tag);
	return (1);
}

/*
 * Writes the component instance into the registry
 * file.
 */
static int
write_component_instance(Xml_reg_io *xr, int start)
{
	Xml_tag *tag = _wsreg_xtag_create();
	Xml_file_io *xf = xr->pdata->xml_file;

	Wsreg_component **components = xr->get_components(xr);
	char instancestring[10];

	(void) sprintf(instancestring, "%d", components[start]->instance);
	tag->set_tag(tag, tag_map, "compinstance");
	tag->set_value_string(tag, instancestring);
	xf->write_tag(xf, tag);

	if (components[start]->parent != NULL) {
		_Wsreg_instance *parent =
		    (_Wsreg_instance*)components[start]->parent;
		(void) write_instance(xr, "parent", parent);
	}
	if (components[start]->children != NULL) {
		(void) write_component_references(xr,
		    "children",
		    components[start]->children);
	}

	/*
	 * The component type is "PRODUCT", "FEATURE", or
	 * "COMPONENT"
	 */
	tag->set_tag(tag, tag_map, "comptype");
	tag->set_value_string(tag, "COMPONENT");
	switch (components[start]->component_type) {
	case WSREG_PRODUCT:
		tag->set_value_string(tag, "PRODUCT");
		break;

	case WSREG_FEATURE:
		tag->set_value_string(tag, "FEATURE");
		break;

	case WSREG_COMPONENT:
		tag->set_value_string(tag, "COMPONENT");
		break;
	}
	xf->write_tag(xf, tag);
	xf->write_close_tag(xf, tag);

	if (components[start]->location != NULL) {
		tag->set_tag(tag, tag_map, "location");
		tag->set_value_string(tag, components[start]->location);
		xf->write_tag(xf, tag);
		xf->write_close_tag(xf, tag);
	}
	if (components[start]->uninstaller != NULL) {
		tag->set_tag(tag, tag_map, "uninstaller");
		tag->set_value_string(tag, components[start]->uninstaller);
		xf->write_tag(xf, tag);
		xf->write_close_tag(xf, tag);
	}
	if (components[start]->backward_compatible != NULL) {
		(void) write_versions(xr, "compatible",
		    (List*)components[start]->backward_compatible);
	}

	if (components[start]->dependent != NULL) {
		(void) write_component_references(xr,
		    "dependent",
		    (List*)components[start]->dependent);
	}

	if (components[start]->required != NULL) {
		(void) write_component_references(xr,
		    "required",
		    (List*)components[start]->required);
	}

	if (components[start]->app_data != NULL) {
		List *ad = (List*)components[start]->app_data;
		(void) write_paired_data(xr, "data",
		    "key",
		    "value",
		    ad);
	}

	tag->set_tag(tag, tag_map, "compinstance");
	tag->set_value_string(tag, NULL);
	xf->write_close_tag(xf, tag);

	tag->free(tag);
	return (1);
}

/*
 * Writes 'c' components into the registry file.
 */
static int
write_component_version(Xml_reg_io *xr, int start, int c)
{
	int i;
	Wsreg_component **components = xr->get_components(xr);
	Xml_tag *tag = _wsreg_xtag_create();
	Xml_file_io *xf = xr->pdata->xml_file;

	tag->set_tag(tag, tag_map, "compversion");
	tag->set_value_string(tag, components[start]->version);
	xf->write_tag(xf, tag);

	if (components[start]->unique_name != NULL) {
		tag->set_tag(tag, tag_map, "uniquename");
		tag->set_value_string(tag, components[start]->unique_name);
		xf->write_tag(xf, tag);
		xf->write_close_tag(xf, tag);
	}
	if (components[start]->display_name != NULL) {
		(void) write_paired_data(xr,
		    "displayname",
		    "language",
		    "localizedname",
		    components[start]->display_name);
	}
	if (components[start]->vendor != NULL) {
		tag->set_tag(tag, tag_map, _tagtab[VENDOR]);
		tag->set_value_string(tag, components[start]->vendor);
		xf->write_tag(xf, tag);
		xf->write_close_tag(xf, tag);
	}

	for (i = start; i < start + c; i++) {
		(void) write_component_instance(xr, i);
	}
	tag->set_tag(tag, tag_map, "compversion");
	tag->set_value_string(tag, NULL);
	xf->write_close_tag(xf, tag);

	tag->free(tag);
	return (i);
}

/*
 * Writes 'c' components into the registry file.
 */
static int
write_component(Xml_reg_io *xr, int start, int c)
{
	int i;
	int count = 0;
	Wsreg_component **components = xr->get_components(xr);
	Xml_tag *tag = _wsreg_xtag_create();
	Xml_file_io *xf = xr->pdata->xml_file;

	tag->set_tag(tag, tag_map, "compid");
	tag->set_value_string(tag, components[start]->id);
	xf->write_tag(xf, tag);

	for (i = start; i < start + c; i += count) {
		count = 1;

		/*
		 * Be sure the count does not increment
		 * beyond c!
		 *
		 * Ensure that the version strings to be compared exist.
		 * It is technically possible to register a component
		 * with no version string.
		 */
		while (count < c &&
		    components[i + count] != NULL &&
		    components[i]->version &&
		    components[i + count]->version &&
		    strcmp(components[i]->version,
			components[i + count]->version) == 0) {
			count++;
		}
		if (components[i] && components[i + count] &&
		    components[i]->version == NULL &&
		    components[i + count]->version == NULL)
			count++;

		(void) write_component_version(xr, i, count);
	}
	xf->write_close_tag(xf, tag);

	tag->free(tag);
	return (i);
}

/*
 * Writes all components into the registry file.
 */
static void
write_components(Xml_reg_io *xr)
{
	int i;
	int count;
	Wsreg_component **components = xr->get_components(xr);

	if (components != NULL) {
		i = 0;
		while (components[i] != NULL) {
			count = 1;
			while (components[i + count] != NULL &&
			    strcmp(components[i]->id,
				components[i + count]->id) == 0) {
				count++;
			}

			(void) write_component(xr, i, count);

			i = i+count;
		}
	}
}


/*
 * Creates a component reference.
 */
static _Wsreg_instance *
create_instance(char *compID, int instance, char *version)
{
	_Wsreg_instance *comp = NULL;
	String_util *sutil = _wsreg_strutil_initialize();
	if (compID != NULL && version != NULL) {
		comp = wsreg_malloc(sizeof (_Wsreg_instance));
		comp->id = sutil->clone(compID);
		comp->version = sutil->clone(version);
		comp->instance = instance;
	}
	return (comp);
}
