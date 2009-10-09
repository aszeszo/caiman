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

#include <Python.h>
#include <structmember.h>
#include <libintl.h>
#include "libaiscf.h"
#include "libaiscf_instance.h"
#include "libaiscf_service.h"

/* ~~~~~~~~~~~~~~~~ */
/* Private Funtions */
/* ~~~~~~~~~~~~~~~~ */

/*
 * Function:    AIservice_raise_ai_errno_error
 * Description: Set Python error flag and raise appropriate errors for
 *		ai_errno_t values
 * Parameters:
 *   args -     self - AIserver pointer
 *		ret  - error to report on
 *
 * Returns nothing
 * Scope:
 *      Private
 */

static void
AIservice_raise_ai_errno_error(AIservice *self, ai_errno_t ret) {
	char *errStr;
	/*
	 * Override for any errors which should have specific errors when
	 * called out of the AIservice context than that of AIinstance
	 */
	switch (ret) {
		case AI_NO_SUCH_PG: {
			int len = (PyString_Size(self->serviceName)+
			    strlen(gettext("No such service name: ")) + 1);
			errStr = calloc(len, sizeof (char));
			if (NULL == errStr) {
				PyErr_NoMemory();
			}
			(void) snprintf(errStr, len,
			    gettext("No such service name: %s"),
			    PyString_AsString(self->serviceName));
			PyErr_SetString(PyExc_KeyError, errStr);
			free(errStr);
			break;
		}
		/*
		 * For all else, call the AIinstance version of
		 * raise_ai_errno_error()
		 */
		default:
			AIinstance_raise_ai_errno_error(self->instance, ret);
			break;
	}
}

/*
 * Function:    AIservice_new
 * Description: Allocate RAM for an AIservice object
 *
 * Returns	AIservice object, NULL on failure
 * Scope:
 *      Private
 */

PyObject*
AIservice_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	AIservice *self;

	self = (AIservice *)type->tp_alloc(type, 0);
	if (NULL != self) {
		self->instance = NULL;
		self->serviceName = PyString_FromString("");
		if (NULL == self->serviceName) {
			Py_DECREF(self);
			PyErr_SetString(PyExc_MemoryError,
			    gettext("Could not allocate service name"));
			return (NULL);
		}
	} else {
		PyErr_SetString(PyExc_MemoryError,
		    gettext("Could not allocate AI service object"));
	}
	return ((PyObject *)self);
}

/*
 * Function:    AIservice_init
 * Description: Initialize data structures for an AIservice object
 *
 * Parameters	instance - AISCF instance
 *		service	 - SMF property group name
 *
 * Returns	-1 on failure, 0 on success
 * Scope:
 *      Private
 */

int
AIservice_init(AIservice *self, PyObject *args)
{
	ai_errno_t ret;
	AISCF *instance = NULL;
	PyObject *service_name = NULL;

	if (!PyArg_ParseTuple(args, "O!S", &AISCFType, &instance,
	    &service_name)) {
		return (-1);
	}

	/* Assign AI SCF Instance First */
	Py_XDECREF(self->instance);
	self->instance = instance;
	Py_INCREF(self->instance);

	/* Check For Service */
	/* First Get Service */
	int len = (strlen("AI") + PyString_Size(service_name) + 1);
	char svcStr[len];
	(void) snprintf(svcStr, len, "AI%s", PyString_AsString(service_name));
	ret = ai_get_pg((self->instance)->scfHandle, svcStr);

	/* Next Check If Service Exists */
	if (ret != AI_SUCCESS) {
		AIservice_raise_ai_errno_error(self, ret);
		Py_INCREF(service_name);
		PyErr_SetObject(PyExc_KeyError, service_name);
		return (-1);
	}

	Py_DECREF(self->serviceName);
	self->serviceName = service_name;
	Py_INCREF(self->serviceName);
	return (0);
}

/*
 * Function:    AIservice_dealloc
 * Description: Deallocate RAM used by an AIservice object
 *
 * Parameters	AIservice instance
 * Scope:
 *      Private
 */

static void
AIservice_dealloc(AIservice *self)
{
	Py_XDECREF(self->instance);
	Py_XDECREF(self->serviceName);
	self->ob_type->tp_free((PyObject*)self);
}

/*
 * Function:    AIservice_get_prop_names_and_values
 * Description: Provide all properties and values for a service
 * Parameters:
 *   args -     Takes an AIservice
 *
 * Returns a dictionary of keys and values:
 * Scope:
 *      Private
 */

static PyObject *
AIservice_get_prop_names_and_values(AIservice *self)
{
	ai_errno_t ret;
	ai_prop_list_t *prop_list, *prop_current;
	PyObject *dict, *tmp;

	int len = (strlen("AI") + PyString_Size(self->serviceName) + 1);
	char svcStr[len];
	(void) snprintf(svcStr, len, "AI%s",
	    PyString_AsString(self->serviceName));
	ret = ai_read_all_props_in_pg((self->instance)->scfHandle, svcStr,
	    &prop_list);

	if (ret == AI_NO_MEM) {
		PyErr_SetString(PyExc_MemoryError,
		    gettext("Could not allocate property group list"));
		return (NULL);
	} else if (ret != AI_SUCCESS) {
		AIservice_raise_ai_errno_error(self, ret);
		return (NULL);
	}

	dict = PyDict_New();
	if (NULL == dict) {
		ai_free_prop_list(prop_list);
		return (NULL);
	}
	for (prop_current = prop_list; prop_current != NULL;
	    prop_current = prop_current->next) {
		/* Check if property has a value */
		if (NULL == prop_current->name) {
			continue;
		} else if (NULL == prop_current->valstr) {
			if (0 != PyDict_SetItemString(dict,
			    prop_current->name, Py_None)) {
				Py_DECREF(dict);
				ai_free_prop_list(prop_list);
				return (NULL);
			}
		} else {
			tmp = PyString_FromString(prop_current->valstr);
			if (0 != PyDict_SetItemString(dict,
			    prop_current->name, tmp)) {
				Py_DECREF(tmp);
				Py_DECREF(dict);
				ai_free_prop_list(prop_list);
				return (NULL);
			}
			Py_DECREF(tmp);
		}
	}
	ai_free_prop_list(prop_list);
	return (dict);
}

/*
 * Function:    AIservice_Str
 * Description: Provide a string representation of SMF properties
 * Parameters:
 *   args -     Takes an AIservice PyObject
 *
 * Returns a string of keys and values:
 * Scope:
 *      Private
 */

static PyObject * AIservice_Str(PyObject *self) {
	return PyObject_Str(
	    AIservice_get_prop_names_and_values((AIservice *)self));
}

/*
 * Function:    AIservice_set_subscript
 * Description: Set the value for a service's property
 * Parameters:
 *   args -     AIservice
 *		A PyObject subscript string
 *		A PyObject string to set subscript to
 *
 * Returns 0 on success, -1 on failure
 * Scope:
 *      Private
 */

static int
AIservice_set_subscript(AIservice *self, PyObject *subscript, PyObject *value)
{
	ai_errno_t ret;
	if (!PyString_Check(subscript)) {
		PyErr_SetString(PyExc_IndexError,
		    gettext("Only string objects supported for AI service "
		    "property names"));
		return (-1);
	}
	/* We are deleting this key */
	if (NULL == value) {
		int len = (strlen("AI") + PyString_Size(self->serviceName) + 1);
		char svcStr[len];
		(void) sprintf(svcStr, "AI%s", len,
		    PyString_AsString(self->serviceName));
		ret = ai_delete_property((self->instance)->scfHandle, svcStr,
		    PyString_AsString(subscript));
		if (ret == AI_SUCCESS) {
			return (0);
		}
		AIservice_raise_ai_errno_error(self, ret);
	}
	/* We got a non-string key */
	else if (!PyString_Check(value)) {
		PyErr_SetString(PyExc_TypeError,
		    gettext("Only string objects supported for AI service "
		    "property values"));
	/* Return the key requested */
	} else {
		int len = (strlen("AI") + PyString_Size(self->serviceName) + 1);
		char svcStr[len];
		(void) snprintf(svcStr, len, "AI%s",
		    PyString_AsString(self->serviceName));
		ret = ai_set_property((self->instance)->scfHandle,
		    svcStr, PyString_AsString(subscript),
		    PyString_AsString(value));
		if (ret == AI_SUCCESS) {
			return (0);
		}
		AIservice_raise_ai_errno_error(self, ret);
	}
	return (-1);
}


/*
 * Function:    AIservice_subscript
 * Description: Provide value for a service's property
 * Parameters:
 *   args -     AIservice
 *		A PyObject subscript string to query for
 *
 * Returns a PyString representing the value of the requested key
 * Scope:
 *      Private
 */

static PyObject *
AIservice_subscript(AIservice *self, PyObject *subscript)
{
	PyObject *value = NULL, *keysAndValues = NULL;
	keysAndValues = AIservice_get_prop_names_and_values(self);

	if (NULL == keysAndValues) {
		return (NULL);
	}

	value = PyDict_GetItem(keysAndValues, subscript);
	if (NULL == value) {
		Py_INCREF(subscript);
		PyErr_SetObject(PyExc_KeyError, subscript);
		Py_DECREF(keysAndValues);
		return (NULL);
	}
	/* take ownership of value before giving up keysAndValues */
	Py_INCREF(value);
	Py_DECREF(keysAndValues);

	return (value);
}

/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
/* Public Funtions -- All Accessible Through Python */
/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */

/* Members for AI Service Type Object */

static PyMemberDef AIservice_type_members[] = {
	{
		.name = "instance",
		.type = T_OBJECT_EX,
		.offset = offsetof(AIservice, instance),
		.flags = 0,
		.doc = "AI Instance"
	},
	{
		.name = "serviceName",
		.type = T_OBJECT_EX,
		.offset = offsetof(AIservice, serviceName),
		.flags = 0,
		.doc = "AI Service Name"
	}, {NULL}  /* Sentinel */
};

/* Methods for AI Service Type Object */

static PyMethodDef AIservice_type_methods[] = {
	{
		.ml_name = "as_dict",
		.ml_meth = (PyCFunction)AIservice_get_prop_names_and_values,
		.ml_flags = METH_NOARGS,
		.ml_doc = "Get a dict of service properties and values"
	},
	{NULL} /* Sentinel */
};

/* Mapping Methods for AI Service Type Object */

PyMappingMethods AIservice_type_mapping = {
	.mp_subscript = (binaryfunc)AIservice_subscript,
	.mp_ass_subscript = (objobjargproc)AIservice_set_subscript,
};

/* Members for AI Service Type Object */

static PyMemberDef AISCF_type_members[] = {
	{
		.name = "serviceName",
		.type = T_OBJECT_EX,
		.offset = offsetof(AIservice, serviceName),
		.flags = 0,
		.doc = "AI Service Name"
	},
	{NULL}  /* Sentinel */
};

/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */
/* Define AIservice Object Type */
/* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */

PyTypeObject AIserviceType = {
	PyObject_HEAD_INIT(NULL)
	.ob_size = 0,
	.tp_name = "_libaiscf._AIservice",
	.tp_str = AIservice_Str,
	.tp_basicsize = sizeof (AIservice),
	.tp_dealloc = (destructor)AIservice_dealloc,
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = "AutoInstaller Service object",
	.tp_methods = AIservice_type_methods,
	.tp_members = AIservice_type_members,
	.tp_init = (initproc)AIservice_init,
	.tp_new = AIservice_new,
	.tp_as_mapping = &AIservice_type_mapping
};
