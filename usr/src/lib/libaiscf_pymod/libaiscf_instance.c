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
#include <stdio.h>
#include <libintl.h>
#include "libaiscf.h"
#include "libaiscf_instance.h"
#include "libaiscf_service.h"

/*
 * Function:    AIinstance_raise_ai_errno_error
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

void
AIinstance_raise_ai_errno_error(AISCF *self, ai_errno_t ret)
{
	char *errStr;
	switch (ret) {
		case AI_NO_PERMISSION:
			PyErr_SetString(PyExc_SystemError,
			    ai_strerror(ret));
			break;
		case AI_NO_MEM:
			PyErr_NoMemory();
			break;
		case AI_NO_SUCH_PG:
			PyErr_SetString(PyExc_KeyError,
			    ai_strerror(ret));
			break;
		case AI_PG_ITER_ERR:
			PyErr_SetString(PyExc_RuntimeError,
			    ai_strerror(ret));
			break;
		case AI_NO_SUCH_INSTANCE:
			errStr = calloc(PyString_Size(self->instanceName) +
			    strlen(gettext("No such instance name: ") + 1),
			    sizeof (char));
			if (NULL == errStr) {
				PyErr_NoMemory();
			}
			sprintf(errStr,
			    gettext("No such instance name: %s"),
			    PyString_AsString(self->instanceName));
			PyErr_SetString(PyExc_KeyError, errStr);
			free(errStr);
			break;
		case AI_NO_SUCH_PROP:
			PyErr_SetString(PyExc_KeyError,
			    ai_strerror(ret));
			break;
		case AI_SYSTEM_ERR:
			PyErr_SetString(PyExc_SystemError,
			    ai_strerror(ret));
			break;
		case AI_TRANS_ERR:
			PyErr_SetString(PyExc_SystemError,
			    ai_strerror(ret));
			break;
		case AI_CONFIG_ERR:
			PyErr_SetString(PyExc_SystemError,
			    ai_strerror(ret));
			break;
		case AI_PG_CREAT_ERR:
			PyErr_SetString(PyExc_SystemError,
			    ai_strerror(ret));
			break;
		case AI_PG_DELETE_ERR:
			PyErr_SetString(PyExc_SystemError,
			    ai_strerror(ret));
			break;
		case AI_PG_EXISTS_ERR:
			PyErr_SetString(PyExc_ValueError,
			    ai_strerror(ret));
			break;
		case AI_INVAL_ARG:
			PyErr_SetString(PyExc_TypeError,
			    ai_strerror(ret));
			break;
		default:
			PyErr_SetString(PyExc_StandardError,
			    ai_strerror(ret));
			break;
	}
}

/*
 * Function:    AISCF_new
 * Description: Initialize RAM for a new AISCF object
 *
 * Returns	AISCF object, NULL on failure
 * Scope:	Private
 *
 */

static PyObject *
AISCF_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	AISCF *self;

	self = (AISCF *)type->tp_alloc(type, 0);
	if (NULL != self) {
		self->scfHandle = NULL;
		self->instanceName = PyString_FromString("");
		if (NULL == self->instanceName) {
			Py_DECREF(self);
			PyErr_SetString(PyExc_MemoryError,
			    gettext("Could not allocate AISCF instance"));
			return (NULL);
		}
		self->FMRI = PyString_FromString("");
		if (NULL == self->FMRI) {
			Py_DECREF(self);
			PyErr_SetString(PyExc_MemoryError,
			    gettext("Could not allocate FMRI storage"));
			return (NULL);
		}
	} else {
		PyErr_SetString(PyExc_MemoryError,
		    gettext("Could not allocate AISCF object"));
	}
	return ((PyObject *)self);
}

/*
 * Function:    AISCF_init
 * Description: Initialize data structures for an AISCF object
 *
 * Parameters	instance - SMF instance name (i.e. default)
 *		FMRI	 - SMF FMRI (i.e. network/physical)
 *
 * Returns	-1 on failure, 0 on success
 * Scope:	Private
 *
 */

static int
AISCF_init(AISCF *self, PyObject *args, PyObject *kwds)
{
	ai_errno_t ret;
	scfutilhandle_t *tmpHandle = NULL;
	char *instance_name = NULL, *FMRI = NULL;
	static char *kwlist[] = {"instance", "FMRI", NULL};

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|ss", kwlist,
	    &instance_name, &FMRI)) {
		return (-1);
	}

	/* Get SMF FMRI */
	Py_DECREF(self->FMRI);
	if (FMRI != NULL) {
		self->FMRI = PyString_FromString(FMRI);
	} else {
		/* Default SMF FMRI */
		self->FMRI = PyString_FromString(AI_DEFAULT_SERVER_SVC_NAME);
	}

	/* PyArgs will free original FMRI pointer */
	FMRI = PyString_AsString(self->FMRI);

	/* Allocate SCF Instance Handle */
	if (self->scfHandle != NULL) {
		ai_scf_fini(self->scfHandle);
	}
	self->scfHandle = libaiscf_scf_init(FMRI);
	if (NULL == self->scfHandle) {
		/* should error about unable to SCF init */
		if (scf_error()) {
			PyErr_SetString(PyExc_SystemError,
			    scf_strerror(scf_error()));
		} else {
			PyErr_SetString(PyExc_MemoryError,
			    gettext("Could not allocate SCF handle"));
		}
		Py_DECREF(self);
		return (-1);
	}

	/* Get AI SCF Instance First */
	Py_DECREF(self->instanceName);
	if (instance_name != NULL) {
		/* self->instanceName = PyString_FromString(instance_name); */
		PyErr_SetString(PyExc_NotImplementedError,
		    gettext("Instance names not yet implemented"));

	} else {
		/* Default SMF Service Instance */
		self->instanceName = PyString_FromString("default");
	}

	instance_name = PyString_AsString(self->instanceName);
	ret = ai_get_instance(self->scfHandle, instance_name);
	if (ret != AI_SUCCESS) {
		ai_scf_fini(self->scfHandle);
		AIinstance_raise_ai_errno_error(self, ret);
		return (-1);
	}
	return (0);
}

/*
 * Function:    AISCF_dealloc
 * Description: Deallocate RAM used by an AISCF object
 *
 * Parameters	AISCF object to deallocate
 *
 * Scope:	Private
 *
 */

static void
AISCF_dealloc(AISCF* self)
{
	Py_XDECREF(self->instanceName);
	Py_XDECREF(self->FMRI);
	ai_scf_fini(self->scfHandle);
	self->scfHandle = NULL;
	self->ob_type->tp_free((PyObject*)self);
}

/* ~~~~~~~~~~~~~~~ */
/* Public Funtions */
/* ~~~~~~~~~~~~~~~ */

/*
 * Function:    get_instance_state
 * Description: Return SMF instance state as SMF_STATE_STRING string
 * Parameters:
 *   args -     AISCF Instance
 *		closure is unused but required by API
 *
 * Returns string, thorws an exception on error
 * Scope:
 *      Public
 * TODO: Should return a SMF State Object which can represent more than the
 *	 current state but perhaps if the instance is transitioning, etc.
 */

static PyObject *
get_instance_state(AISCF *self, void *closure)
{
	ai_errno_t	ret;
	PyObject	*return_string;
	char		*state = NULL;

	/* Ensure Instance Exists */
	ret = ai_get_instance(self->scfHandle,
	    PyString_AsString(self->instanceName));
	if (ret != AI_SUCCESS) {
		AIinstance_raise_ai_errno_error(self, ret);
		return (NULL);
	}

	int len = (PyString_Size(self->FMRI) + strlen(":") +
	    PyString_Size(self->instanceName) + 1);
	char svcStr[len];
	(void) snprintf(svcStr, len, "%s:%s", PyString_AsString(self->FMRI),
	    PyString_AsString(self->instanceName));

	/* Get Service State */
	state = smf_get_state(svcStr);

	if (state == NULL) {
		PyErr_SetString(PyExc_SystemError,
		    scf_strerror(scf_error()));
		return (NULL);
	}
	return_string = PyString_FromString(state);
	free(state);
	return (return_string);
}

/*
 * Function:    set_instance_state
 * Description: Request a state change for an SMF instance
 * Parameters:
 *   args -     AISCF Instance
 *		PyObject string representing state to change to
 *		Supported states are:
 *		CLEAR, DEGRADE, DISABLE, ENABLE, MAINTENANCE, RESTART,
 *		RESTORE, REFRESH
 *		closure is unusued but required by API
 *
 * Returns none, thorws an exception on error
 * Scope:
 *      Public
 * TODO: Should accept a SMF State Object which can represent more than the
 *	 current state but perhaps if the state requested is temporary, etc.
 */

static int
set_instance_state(AISCF *self, PyObject *arg, void *closure)
{
	int		ret;
	char		*state, *tmp;

	state = PyString_AsString(arg);

	/* Ensure Instance Exists */
	ret = ai_get_instance(self->scfHandle,
	    PyString_AsString(self->instanceName));
	if (ret != AI_SUCCESS) {
		AIinstance_raise_ai_errno_error(self, ret);
		return (-1);
	}

	int len = (PyString_Size(self->FMRI) + strlen(":") +
	    PyString_Size(self->instanceName) + 1);
	char svcStr[len];
	(void) snprintf(svcStr, len, "%s:%s", PyString_AsString(self->FMRI),
	    PyString_AsString(self->instanceName));

	/* Delete Service */

	/* Clear is synonymous with restore */
	if (strcasecmp(state, "CLEAR") == 0) {
		ret = smf_restore_instance(svcStr);
	} else if (strcasecmp(state, "DISABLE") == 0) {
		ret = smf_disable_instance(svcStr, 0);
	} else if (strcasecmp(state, "DEGRADE") == 0) {
		ret = smf_degrade_instance(svcStr, 0);
	} else if (strcasecmp(state, "ENABLE") == 0) {
		ret = smf_enable_instance(svcStr, 0);
	} else if (strcasecmp(state, "MAINTENANCE") == 0) {
		ret = smf_maintain_instance(svcStr, 0);
	} else if (strcasecmp(state, "RESTART") == 0) {
		ret = smf_restart_instance(svcStr);
	} else if (strcasecmp(state, "REFRESH") == 0) {
		ret = smf_refresh_instance(svcStr);
	/* Restore is synonymous with clear */
	} else if (strcasecmp(state, "RESTORE") == 0) {
		ret = smf_restore_instance(svcStr);
	} else {
		PyErr_SetString(PyExc_ValueError,
		    gettext("Unsupported state"));
		return (-1);
	}

	if (ret != 0) {
		PyErr_SetString(PyExc_SystemError,
		    scf_strerror(scf_error()));
		return (-1);
	}

	return (0);
}

/*
 * Function:    new_service
 * Description: Create an AI service associated with the SMF instance
 * Parameters:
 *   args -     AISCF Instance
 *		Service Name
 *
 * Returns none, thorws an exception on error
 * Scope:
 *      Public
 */
PyObject *
new_service(AISCF *self, PyObject *args)
{
	ai_errno_t	ret;
	PyObject	*service_name;

	if (!PyArg_ParseTuple(args, "S", &service_name)) {
		return (NULL);
	}

	int len = (strlen("AI") + PyString_Size(service_name) + 1);
	char svcStr[len];
	(void) snprintf(svcStr, len, "AI%s",
	    PyString_AsString(service_name));

	ret = ai_get_pg(self->scfHandle, svcStr);
	/* create property group */
	if (ret == AI_NO_SUCH_PG) {
		ret = ai_create_pg(self->scfHandle, svcStr);
		if (ret != AI_SUCCESS) {
			AIinstance_raise_ai_errno_error(self, ret);
			return (NULL);
		}
	/* property group already exists */
	} else if (ret == AI_SUCCESS) {
		AIinstance_raise_ai_errno_error(self, AI_PG_EXISTS_ERR);
		return (NULL);
	} else {
		AIinstance_raise_ai_errno_error(self, ret);
		return (NULL);
	}

	Py_INCREF(Py_None);
	return (Py_None);
}

/*
 * Function:    del_service
 * Description: Delete an AI service associated with the SMF instance
 * Parameters:
 *   args -     AISCF Instance
 *		Service Name
 *
 * Returns none, thorws an exception on error
 * Scope:
 *      Public
 */

PyObject *
del_service(AISCF *self, PyObject *args)
{
	ai_errno_t	ret;
	char		*service_name;

	if (!PyArg_ParseTuple(args, "s", &service_name)) {
		return (NULL);
	}

	int len = (strlen(service_name) + strlen("AI") + 1);
	char svcStr[len];
	(void) snprintf(svcStr, len, "AI%s", service_name);

	/* Ensure Service Exists */
	ret = ai_get_pg(self->scfHandle, svcStr);

	/* Check Service Exists */
	if (ret != AI_SUCCESS) {
		AIinstance_raise_ai_errno_error(self, ret);
		return (NULL);
	}

	/* Delete Service */
	ret = ai_delete_pg(self->scfHandle, svcStr);
	if (ret != AI_SUCCESS) {
		AIinstance_raise_ai_errno_error(self, ret);
		return (NULL);
	}

	Py_INCREF(Py_None);
	return (Py_None);
}

/*
 * Function:    services
 * Description: Return a list of AI services associated with the SMF instance
 * Parameters:
 *   args -     AISCF Instance
 *
 * Returns a pointer to a python object:
 *      List with AI service
 * Scope:
 *      Public
 */

PyObject *
get_services(AISCF *self)
{
	ai_errno_t ret;
	ai_pg_list_t *service_head, *service;
	PyObject *list = NULL, *tmp = NULL;

	/* Get Services */
	ret = ai_get_pgs(self->scfHandle, &service_head);

	if (ret != AI_SUCCESS) {
		if (service_head != NULL) {
			ai_free_pg_list(service_head);
		}
		AIinstance_raise_ai_errno_error(self, ret);
		return (NULL);
	}

	list = PyList_New(0);
	if (NULL != service_head) {
		for (service = service_head; service != NULL;
		    service = service->next) {
			if (NULL != service->pg_name) {
				tmp = PyString_FromString(service->pg_name);
				PyList_Append(list,
				    tmp);
				Py_DECREF(tmp);
			}
		}
	}
	ai_free_pg_list(service_head);
	return (list);
}

/* Properties for AI SCF Type Object */

static PyGetSetDef AISCF_type_properties[] = {
	{
		.name = "state",
		.get = (getter)get_instance_state,
		.set = (setter)set_instance_state,
		.doc = "AISCF Instance Run State\nSupports the following "
		    "states: CLEAR, DEGRADE, DISABLE, ENABLE, MAINTENANCE, "
		    "RESTART, RESTORE, REFRESH"
	}, {NULL}  /* Sentinel */
};

/* Members for AI SCF Type Object */

static PyMemberDef AISCF_type_members[] = {
	{
		.name = "FMRI",
		.type = T_OBJECT_EX,
		.offset = offsetof(AISCF, FMRI),
		.flags = 0,
		.doc = "AISCF Base FMRI"
	},
	{
		.name = "instanceName",
		.type = T_OBJECT_EX,
		.offset = offsetof(AISCF, instanceName),
		.flags = 0,
		.doc = "AISCF Instance Name"
	}, {NULL}  /* Sentinel */
};

/* Methods for AI SCF Type Object */

static PyMethodDef AISCF_type_methods[] = {
	{
		.ml_name = "services",
		.ml_meth = (PyCFunction)get_services,
		.ml_flags = METH_NOARGS,
		.ml_doc = "Return services associate with an AISCF instance"
	},
	{
		.ml_name = "new_service",
		.ml_meth = (PyCFunction)new_service,
		.ml_flags = METH_VARARGS,
		.ml_doc = "Create a service"
	},
	{
		.ml_name = "del_service",
		.ml_meth = (PyCFunction)del_service,
		.ml_flags = METH_VARARGS,
		.ml_doc = "Delete a service"
	},
	{NULL} /* Sentinel */
};

/* Define AISCF Object Type */

PyTypeObject AISCFType = {
	PyObject_HEAD_INIT(NULL)
	.ob_size = 0,
	.tp_name = "_libaiscf._AISCF",
	.tp_basicsize = sizeof (AISCF),
	.tp_dealloc = (destructor)AISCF_dealloc,
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = "AutoInstaller SCF object",
	.tp_getset = AISCF_type_properties,
	.tp_methods = AISCF_type_methods,
	.tp_members = AISCF_type_members,
	.tp_init = (initproc)AISCF_init,
	.tp_new = AISCF_new
};

/* Private python initialization structure */

static struct PyMethodDef libaiscfMethods[] = {
	{
		.ml_name = "get_services",
		.ml_meth = (PyCFunction)get_services,
		.ml_flags = METH_VARARGS,
		.ml_doc = "Get a list of property group names"
	},
	{NULL, NULL, 0, NULL}
};

/* Initialize Module */

void
init_libaiscf()
{
	PyObject *m;

	if (PyType_Ready(&AISCFType) < 0)
		return;
	if (PyType_Ready(&AIserviceType) < 0)
		return;

	/* PyMODINIT_FUNC; */
	if (NULL == (m = Py_InitModule3("_libaiscf", libaiscfMethods,
	    "Module which implements libaiscf to Python bridge and "
	    "AISCF and AIservice types."))) {
		return;
	}

	Py_INCREF(&AISCFType);
	Py_INCREF(&AIserviceType);
	PyModule_AddObject(m, "_AISCF", (PyObject *)&AISCFType);
	PyModule_AddObject(m, "_AIservice", (PyObject *)&AIserviceType);
}
