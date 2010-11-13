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
 * Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
 */
/*
 * Internet Protocol network interface names and interface indexes
 * software Python library (if_nametoindex, if_indextoname, if_nameindex)
 */
#include <net/if.h>
#include <stdio.h>
#include <libintl.h>

#include <Python.h>

#include "netif.h"

/* exception variable */
PyObject *NetIFError = NULL;

/*
 * netif_if_nameindex:
 *
 * Description:
 *   Python wrapper for the if_nameindex function.
 *
 * Parameters:
 *   self - standard C Python binding self
 *   arg  - standard C Python binding arguments, nothing passed into this
 *          function.
 *
 * Globals:
 *   NetIFError - exception variable, modified
 *
 * Raises:
 *   NoMemory -- OR --
 *   NetIFError - errors occurring from if_nameindex()
 *
 * Returns:
 *   Either:
 *   - dictionary of available interfaces { ifindex:'ifname', ... } -- OR --
 *   - empty dictionary
 */
static PyObject *
netif_if_nameindex(PyObject *self, PyObject *arg)
{
	int i;
	PyObject *index;
	PyObject *name;
	PyObject *dict = PyDict_New();
	struct if_nameindex *nameindex = if_nameindex();

	if (nameindex == NULL) {
		if (errno == ENOMEM)
			PyErr_NoMemory();
		else
		{
			char errstr[256];

			sprintf(errstr, gettext(NETIF_ERROR_UNKNOWN), errno);
			PyErr_SetString(NetIFError, errstr);
		}
		return (NULL);
	}

	for (i = 0; nameindex[i].if_name != NULL; i++) {
		index = PyInt_FromLong(nameindex[i].if_index);
		name = PyString_FromString(nameindex[i].if_name);

		PyDict_SetItem(dict, index, name);

		Py_DECREF(index);
		Py_DECREF(name);
	}
	if_freenameindex(nameindex);

	return (dict);
}

/* if_nameindex doc string */
PyDoc_STRVAR(if_nameindex_doc,
"if_nameindex()\n\
\n\
The if_nameindex() function returns a list of tuples of if_nameindex,\n\
as (interface_index, interface_name).");

/*
 * netif_if_nametoindex:
 *
 * Description:
 *   Python wrapper for the if_nametoindex function.
 *
 * Parameters:
 *   self - standard C Python binding self
 *   arg  - standard C Python binding arguments, contains pointers to:
 *
 *        ifname - interface name
 *
 * Globals:
 *   NetIFError - exception variable, modified
 *
 * Raises:
 *   NoMemory -- OR --
 *   NetIFError - for non-matching interface name
 *
 * Returns:
 *   - index integer
 */
PyObject*
netif_if_nametoindex(PyObject *self, PyObject *arg)
{
	char *ifname = PyString_AsString(arg);
	int index = if_nametoindex(ifname);

	if (ifname == NULL)
		return (NULL);

	if (index == 0) {
		if (errno == ENOMEM)
			PyErr_NoMemory();
		else
			PyErr_SetString(NetIFError, gettext(NETIF_ERROR_NAME));
		return (NULL);
	}

	return (PyInt_FromLong(index));
}

/* if_nametoindex doc string */
PyDoc_STRVAR(if_nametoindex_doc,
"if_nametoindex(if_name)\n\
\n\
The if_nametoindex() function returns the interface index corresponding \
to the interface name pointed to by the if_name.");

/*
 * netif_if_indextoname:
 *
 * Description:
 *   Python wrapper for the if_indextoname function.
 *
 * Parameters:
 *   self - standard C Python binding self
 *   arg  - standard C Python binding arguments, contains pointers to:
 *
 *        index - index for the interface
 *
 * Globals:
 *   NetIFError - exception variable, modified
 *
 * Raises:
 *   NoMemory -- OR --
 *   NetIFError - for an invalid interface index
 *
 * Returns:
 *   - interface name string
 */
PyObject*
netif_if_indextoname(PyObject *self, PyObject *arg)
{
	int index = PyInt_AsLong(arg);
	char name[IF_NAMESIZE + 1];
	char *ret = if_indextoname(index, name);

	if (index == -1) {
		if (PyErr_Occurred())
			return (NULL);
		if (errno == ENXIO)
			PyErr_SetString(NetIFError,
			    gettext(NETIF_ERROR_INVALID));
		else if (errno == ENOMEM)
			PyErr_NoMemory();
		else
		{
			char errstr[256];

			sprintf(errstr, gettext(NETIF_ERROR_UNKNOWN), errno);
			PyErr_SetString(NetIFError, errstr);
		}
		return (NULL);
	}

	if (ret == NULL) {
		PyErr_SetString(NetIFError, gettext(NETIF_ERROR_INDEX));
		return (NULL);
	}

	return (PyString_FromString(name));
}

/* if_indextoname doc string */
PyDoc_STRVAR(if_indextoname_doc,
"if_indextoname(if_index)\n\
\n\
The if_indextoname() function maps an interface index into its \
corresponding name.");

/* List of functions exported by this module. */
static PyMethodDef netif_methods[] = {
	{"if_nameindex", netif_if_nameindex,
	    METH_NOARGS, if_nameindex_doc},
	{"if_nametoindex", netif_if_nametoindex,
	    METH_O, if_nametoindex_doc},
	{"if_indextoname", netif_if_indextoname,
	    METH_O, if_indextoname_doc},
	{NULL, NULL} /* Sentinel */
};

/*
 * initnetif:
 *
 * Description:
 *   Initializes the Python extension netif.
 *
 * Parameters:
 *   none
 *
 * Globals:
 *   NetIFError - exception variable, modified
 *
 * Returns:
 *   none
 */
void
initnetif()
{
	PyObject *module;

	/* initialize the netif module */
	module = Py_InitModule("netif", netif_methods);
	if (module == NULL)
		return;

	/* setup the exception variable for netif module */
	NetIFError = PyErr_NewException("netif.NetIFError", NULL, NULL);
	PyModule_AddObject(module, "NetIFError", NetIFError);
}
