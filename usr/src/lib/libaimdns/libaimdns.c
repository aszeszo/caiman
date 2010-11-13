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
#include <Python.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <netdb.h>
#include <libscf.h>
#include <stdlib.h>
#include <strings.h>
#include <libintl.h>

#include "libaimdns.h"

/* exception variable */
PyObject *libaiMDNSError = NULL;
scf_error_t scf_err;

#define	BUF_MAX				1024

/*
 * free_strings:
 *
 * Description:
 *   Frees an array of strings.
 *
 * Parameters:
 *   strings - the array of strings to free.
 *
 * Returns:
 *   void
 */
void
free_strings(char **strings)
{
	int i;

	if (strings != NULL) {
		for (i = 0; strings[i] != NULL; i++)
			free(strings[i]);
		free(strings);
	}
}

/*
 * get_astring_property:
 *
 * Description:
 *   Retrieves the string value of an SMF service property given a
 *   service and a property.
 *
 * Parameters:
 *   fmri     - the fmri that contains the property
 *   propname - the name of the service property
 *
 * Globals:
 *   scf_err - global error variable, modifies
 *
 * Returns:
 *   Either:
 *   - malloc-ed buffer of the property -- OR --
 *   - NULL if an SCF error is encountered.
 */
char *
get_astring_property(char *fmri, char *propname)
{
	scf_handle_t *hdl = NULL;
	scf_property_t *prop = NULL;
	scf_value_t *value = NULL;
	char *rtn = NULL;
	char buf[BUF_MAX];
	char *err_buf;
	int decoded;

	scf_err = 0;
	if ((hdl = scf_handle_create(SCF_VERSION)) == NULL ||
	    scf_handle_bind(hdl) < 0 ||
	    (prop = scf_property_create(hdl)) == NULL) {
		scf_err = scf_error();
		err_buf = (char *)scf_strerror(scf_err);
		goto cleanup;
	}
	snprintf(buf, BUF_MAX, "%s/:properties/%s", fmri, propname);

	decoded = scf_handle_decode_fmri(hdl, buf, NULL, NULL, NULL, NULL, prop,
	    SCF_DECODE_FMRI_EXACT);
	if (decoded < 0 ||
	    (value = scf_value_create(hdl)) == NULL ||
	    scf_property_get_value(prop, value) < 0 ||
	    scf_value_get_astring(value, buf, sizeof (buf)) < 0) {
		scf_err = scf_error();
		err_buf = (char *)scf_strerror(scf_err);
		goto cleanup;
	}
	rtn = strdup(buf);

cleanup:
	if (scf_err != 0)
		PyErr_SetString(libaiMDNSError, err_buf);
	if (value != NULL)
		scf_value_destroy(value);
	if (prop != NULL)
		scf_property_destroy(prop);
	if (hdl != NULL)
		scf_handle_destroy(hdl);

	return (rtn);
}

/*
 * libaimdns_getstrings_property:
 *
 * Description:
 *   Python wrapper for the get_astring_property function defined above.
 *
 * Parameters:
 *   self - standard C Python binding self
 *   arg  - standard C Python binding arguments, contains pointers to:
 *
 *        fmri     - the fmri that contains the property
 *        propname - the name of the service property
 *
 * Globals:
 *   None
 *
 * Returns:
 *   Either:
 *   - A pointer to a Python string -- OR --
 *   - NULL if an SCF error is encountered.
 */
PyObject*
libaimdns_getstring_property(PyObject *self, PyObject *arg)
{
	char *fmri;
	char *propname;
	char *value;
	PyObject *pystring;

	/* get the passed in arguments from Python */
	if (!PyArg_ParseTuple(arg, "|ss", &fmri, &propname))
		return (NULL);

	/* get the property value */
	value = get_astring_property(fmri, propname);

	/* check the return value and respond appropriately */
	if (scf_err != 0)
		return (NULL);

	if (value != NULL) {
		pystring = PyString_FromString(value);
		free(value);
		return (pystring);
	}
	else
		return (NULL);
}

/* getstring_property doc string */
PyDoc_STRVAR(libaimdns_getstring_property_doc,
"getstring_property(fmri, propname)\n\
\n\
The getstring_property() function returns the property value of an SMF service \
fmri for a property key in the form of a string.");

/*
 * get_astrings_property:
 *
 * Description:
 *   Retrieves the string values of an SMF service property given a
 *   service and a property.
 *
 * Parameters:
 *   fmri     - the fmri that contains the property
 *   propname - the name of the service property
 *
 * Globals:
 *   scf_err - global error variable, modifies
 *
 * Returns:
 *   Either:
 *   - A pointer to an array of string values from
 *     the given SMF property -- OR --
 *   - NULL if an SCF error is encountered.
 */
char **
get_astrings_property(char *fmri, char *propname)
{
	scf_handle_t *hdl = NULL;
	scf_property_t *prop = NULL;
	scf_value_t *value = NULL;
	scf_iter_t *iter = NULL;
	char buf[BUF_MAX];
	char *err_buf;
	int decoded;
	char **thestrings = NULL;
	int ret;
	int error = B_FALSE;
	int i = 0;

	scf_err = 0;
	if ((hdl = scf_handle_create(SCF_VERSION)) == NULL ||
	    scf_handle_bind(hdl) < 0 ||
	    (prop = scf_property_create(hdl)) == NULL) {
		scf_err = scf_error();
		err_buf = (char *)scf_strerror(scf_err);
		goto cleanup;
	}
	snprintf(buf, BUF_MAX, "%s/:properties/%s", fmri, propname);

	decoded = scf_handle_decode_fmri(hdl, buf, NULL, NULL, NULL, NULL, prop,
	    SCF_DECODE_FMRI_EXACT);
	if (decoded < 0 || (iter = scf_iter_create(hdl)) == NULL ||
	    (value = scf_value_create(hdl)) == NULL ||
	    scf_iter_property_values(iter, prop) == -1) {
		scf_err = scf_error();
		err_buf = (char *)scf_strerror(scf_err);
		goto cleanup;
	}

	i = 0;
	bzero(buf, BUF_MAX);
	/* Iterate over the property values within the service */
	while ((ret = scf_iter_next_value(iter, value)) > 0) {
		/* Get the next property value in the service */
		if (scf_value_get_astring(value, buf, sizeof (buf)) < 0) {
			scf_err = scf_error();
			err_buf = (char *)scf_strerror(scf_err);
			error = B_TRUE;
			goto cleanup;
		}

		/* Re-allocate the memory adding a new entry. */
		thestrings = realloc(thestrings, (i+1) * sizeof (char **));
		if (thestrings == NULL) {
			scf_err = SCF_ERROR_NO_MEMORY;
			error = B_TRUE;
			goto cleanup;
		}
		/* Save the value in the array of strings. */
		thestrings[i++] = strdup(buf);
	}

	/* NULL terminate the array of strings. */
	thestrings = realloc(thestrings, (i+1) * sizeof (char **));
	if (thestrings == NULL) {
		scf_err = SCF_ERROR_NO_MEMORY;
		error = B_TRUE;
		goto cleanup;
	}
	thestrings[i] = NULL;

cleanup:
	if (scf_err == SCF_ERROR_NO_MEMORY)
		PyErr_NoMemory();
	else if (scf_err != 0)
		PyErr_SetString(libaiMDNSError, err_buf);
	if (value != NULL)
		scf_value_destroy(value);
	if (prop != NULL)
		scf_property_destroy(prop);
	if (iter != NULL)
		scf_iter_destroy(iter);
	if (hdl != NULL)
		scf_handle_destroy(hdl);

	/*
	 * If an error occurred while reading the values from
	 * the service then free up the strings and return NULL.
	 */
	if (error == B_TRUE && thestrings != NULL) {
		free_strings(thestrings);
		thestrings = NULL;
	}

	return (thestrings);
}

/*
 * libaimdns_getstrings_property:
 *
 * Description:
 *   Python wrapper for the get_astring_property function defined above.
 *
 * Parameters:
 *   self - standard C Python binding self
 *   arg  - standard C Python binding arguments, contains pointers to:
 *
 *        fmri     - the fmri that contains the property
 *        propname - the name of the service property
 *
 * Globals:
 *   None
 *
 * Returns:
 *   Either:
 *   - A pointer to a Python list of Python strings -- OR --
 *   - NULL if an SCF error is encountered.
 */
PyObject*
libaimdns_getstrings_property(PyObject *self, PyObject *arg)
{
	char *fmri;
	char *propname;
	char **values;

	/* get the passed in arguments from Python */
	if (!PyArg_ParseTuple(arg, "|ss", &fmri, &propname))
		return (NULL);

	/* get the property values */
	values = get_astrings_property(fmri, propname);

	/* check the return value and respond appropriately */
	if (scf_err != 0)
		return (NULL);
	if (values != NULL) {
		PyObject *list = PyList_New(0);
		int i;

		/*
		 * iterate through the property strings and
		 * save them in the Python list
		 */
		for (i = 0; values[i] != NULL; i++)
			PyList_Append(list, PyString_FromString(values[i]));

		free_strings(values);

		return (list);
	}
	else
		return (NULL);
}

/* getstrings_property doc string */
PyDoc_STRVAR(libaimdns_getstrings_property_doc,
"getstrings_property(fmri, propname)\n\
\n\
The getstrings_property() function returns the property value of an SMF \
service fmri for a property key in the form of a list.");


/*
 * get_boolean_property:
 *
 * Description:
 *   Retrieves the boolean value of an SMF service property given a
 *   service and a property.
 *
 * Parameters:
 *   fmri     - the fmri that contains the property
 *   propname - the name of the service property
 *
 * Globals:
 *   scf_err - global error variable, modifies
 *
 * Returns:
 *   Either:
 *   - B_TRUE or B_FALSE according to the SMF service -- OR --
 *   - B_FALSE if an SCF error is encountered.
 */
int
get_boolean_property(char *fmri, char *propname)
{
	scf_handle_t *hdl = NULL;
	scf_property_t *prop = NULL;
	scf_value_t *value = NULL;
	int rtn = B_FALSE;
	char buf[BUF_MAX];
	char *err_buf;
	int decoded;
	uint8_t out;

	scf_err = 0;
	if ((hdl = scf_handle_create(SCF_VERSION)) == NULL ||
	    scf_handle_bind(hdl) < 0 ||
	    (prop = scf_property_create(hdl)) == NULL) {
		scf_err = scf_error();
		err_buf = (char *)scf_strerror(scf_err);
		goto cleanup;
	}
	snprintf(buf, BUF_MAX, "%s/:properties/%s", fmri, propname);

	decoded = scf_handle_decode_fmri(hdl, buf, NULL, NULL, NULL, NULL, prop,
	    SCF_DECODE_FMRI_EXACT);
	if ((decoded < 0) || (value = scf_value_create(hdl)) == NULL ||
	    scf_property_get_value(prop, value) < 0 ||
	    scf_value_get_boolean(value, &out) < 0) {
		scf_err = scf_error();
		err_buf = (char *)scf_strerror(scf_err);
		goto cleanup;
	}
	rtn = (int)out;

cleanup:
	if (scf_err != 0)
		PyErr_SetString(libaiMDNSError, err_buf);
	if (value != NULL)
		scf_value_destroy(value);
	if (prop != NULL)
		scf_property_destroy(prop);
	if (hdl != NULL)
		scf_handle_destroy(hdl);

	return (rtn);
}

/*
 * libaimdns_getboolean_property:
 *
 * Description:
 *   Python wrapper for the get_boolean_property function defined above.
 *
 * Parameters:
 *   self - standard C Python binding self
 *   arg  - standard C Python binding arguments, contains pointers to:
 *
 *        fmri     - the fmri that contains the property
 *        propname - the name of the service property
 *
 * Globals:
 *   None
 *
 * Returns:
 *   Either:
 *   - True -- OR -- False
 */
PyObject*
libaimdns_getboolean_property(PyObject *self, PyObject *arg)
{
	char *fmri;
	char *propname;
	int value;

	/* get the passed in arguments from Python */
	if (!PyArg_ParseTuple(arg, "|ss", &fmri, &propname))
		return (NULL);

	/* get boolean property */
	value = get_boolean_property(fmri, propname);

	/* check for error and respond appropriately */
	if (scf_err != 0)
		return (PyBool_FromLong((long)B_FALSE));

	return (PyBool_FromLong((long)value));
}

/* getboolean_property doc string */
PyDoc_STRVAR(libaimdns_getboolean_property_doc,
"getboolean_property(fmri, propname)\n\
\n\
The getboolean_property() function returns the property value of \
an SMF service fmri for a boolean property key.");

/*
 * get_integer_property:
 *
 * Description:
 *   Retrieves the integer value of an SMF service property given a
 *   service and a property.
 *
 * Parameters:
 *   fmri     - the fmri that contains the property
 *   propname - the name of the service property
 *
 * Globals:
 *   scf_err - global error variable, modifies
 *
 * Returns:
 *   Either:
 *   - value of the property according to the SMF service -- OR --
 *   - undefined if an SCF error is encountered.
 */
int
get_integer_property(char *fmri, char *propname)
{
	scf_handle_t *hdl = NULL;
	scf_property_t *prop = NULL;
	scf_value_t *value = NULL;
	int64_t rtn = -1;
	char buf[BUF_MAX];
	char *err_buf;
	int decoded;
	int64_t out = -1;

	scf_err = 0;
	if ((hdl = scf_handle_create(SCF_VERSION)) == NULL ||
	    scf_handle_bind(hdl) < 0 ||
	    (prop = scf_property_create(hdl)) == NULL) {
		scf_err = scf_error();
		err_buf = (char *)scf_strerror(scf_err);
		goto cleanup;
	}
	snprintf(buf, BUF_MAX, "%s/:properties/%s", fmri, propname);

	decoded = scf_handle_decode_fmri(hdl, buf, NULL, NULL, NULL, NULL, prop,
	    SCF_DECODE_FMRI_EXACT);
	if (decoded < 0 || (value = scf_value_create(hdl)) == NULL ||
	    scf_property_get_value(prop, value) < 0 ||
	    scf_value_get_integer(value, &out) < 0) {
		scf_err = scf_error();
		err_buf = (char *)scf_strerror(scf_err);
		goto cleanup;
	}
	rtn = (int64_t)out;

cleanup:
	if (scf_err != 0)
		PyErr_SetString(libaiMDNSError, err_buf);
	if (value != NULL)
		scf_value_destroy(value);
	if (prop != NULL)
		scf_property_destroy(prop);
	if (hdl != NULL)
		scf_handle_destroy(hdl);

	return (rtn);
}

/*
 * libaimdns_getboolean_property:
 *
 * Description:
 *   Python wrapper for the get_integer_property function defined above.
 *
 * Parameters:
 *   self - standard C Python binding self
 *   arg  - standard C Python binding arguments, contains pointers to:
 *
 *        fmri     - the fmri that contains the property
 *        propname - the name of the service property
 *
 * Globals:
 *   None
 *
 * Returns:
 *   Either:
 *   - SMF value -- OR --
 *   - NULL if an error is encountered
 */
PyObject*
libaimdns_getinteger_property(PyObject *self, PyObject *arg)
{
	char *fmri;
	char *propname;
	int value;

	/* get the passed in arguments from Python */
	if (!PyArg_ParseTuple(arg, "|ss", &fmri, &propname))
		return (NULL);

	/* get boolean property */
	value = get_integer_property(fmri, propname);

	/* check for error and respond appropriately */
	if (scf_err != 0)
		return (NULL);

	return (PyLong_FromLong((long)value));
}

/* getinteger_property doc string */
PyDoc_STRVAR(libaimdns_getinteger_property_doc,
"getinteger_property(fmri, propname)\n\
\n\
The getinteger_property() function returns the property value of \
an SMF service fmri for an integer property key.");

/*
 * convert_netmask:
 *
 * Description:
 *   Converts an IPv4 netmask string into a CIDR integer.
 *
 * Parameters:
 *   cmask - IPv4 mask string (always #.#.#.#)
 *
 * Globals:
 *   none
 *
 * Returns:
 *   the converted mask as an int between 0-32.
 */
int
convert_netmask(char *cmask)
{
	int mask;
	int m[4];
	int mask_array[] = { 0, 128, 192, 224, 240, 248, 252, 254, 255 };
	int i;
	int k;

	sscanf(cmask, "%d.%d.%d.%d", &m[3], &m[2], &m[1], &m[0]);

	mask = 0;
	for (i = 0; i < sizeof (mask_array) / sizeof (int); i++)
		for (k = 0; k < sizeof (m) / sizeof (int); k++)
			if (m[k] == mask_array[i])
				mask += i;

	return (mask);
}

/*
 * getifaddrs:
 *
 * Description:
 *   Gets the available physical interfaces on a system and stores those in
 *   a dictionary with the name of the interface as the key and the IP address
 *   associated with it as the value.
 *
 * Parameters:
 *   none
 *
 * Returns:
 *   Either:
 *     - a dictionary of available interfaces -- OR --
 *     - a blank dictionary indicating no interfaces are available.
 */
PyObject *
libaimdns_getifaddrs(PyObject *self, PyObject *arg)
{
	struct ifaddrs *ifap, *head;
	char name[NI_MAXHOST];
	char tmp[NI_MAXHOST];
	int socksize = sizeof (struct sockaddr);
	struct sockaddr *sock;
	int mask;
	PyObject *dict = PyDict_New();
	PyObject *key;
	PyObject *value;

	/* get all the interfaces on the system */
	if (getifaddrs(&ifap) == -1) {
		PyErr_SetString(libaiMDNSError,
		    "could not get inferface addresses");
		return (dict);
	}

	/* iterate over the interface linked list. */
	head = ifap;
	while (ifap != NULL) {
		/* skip POINT To POINT interfaces */
		if (ifap->ifa_flags & IFF_POINTOPOINT) {
			ifap = ifap->ifa_next;
			continue;
		}

		/* skip Loopback interfaces */
		if (ifap->ifa_flags & IFF_LOOPBACK) {
			ifap = ifap->ifa_next;
			continue;
		}

		/* convert the socket address to a readable string */
		sock = (struct sockaddr *)ifap->ifa_addr;
		bzero(name, sizeof (name));
		if (getnameinfo(sock, socksize, name, sizeof (name),
		    tmp, sizeof (tmp), NI_NUMERICHOST) == 0) {
			/* get the netmask */
			mask = -1;
			sock = (struct sockaddr *)ifap->ifa_netmask;
			if (getnameinfo(sock, socksize, tmp, sizeof (tmp),
			    NULL, 0, NI_NUMERICHOST) == 0)
				mask = convert_netmask(tmp);

			/* save the ifname and IP address in the dictionary */
			key = PyString_FromString(ifap->ifa_name);
			if (mask == -1)
				value = PyString_FromString(name);
			else
			{
				snprintf(tmp, NI_MAXHOST, "%s/%d", name, mask);
				value = PyString_FromString(tmp);
			}
			PyDict_SetItem(dict, key, value);
			Py_DECREF(key);
			Py_DECREF(value);
		}
		ifap = ifap->ifa_next;
	}
	freeifaddrs(head);

	return (dict);
}

/* getifaddrs doc string */
PyDoc_STRVAR(libaimdns_getifaddrs_doc,
"getifaddrs()\n\
\n\
The getifaddrs() function returns a dictionary from getifaddrs,\n\
as { interface:ip-address/netmask }.");

/* List of functions exported by this module. */
static PyMethodDef libaimdns_methods[] = {
	{"getstring_property", libaimdns_getstring_property,
	    METH_VARARGS, libaimdns_getstring_property_doc},
	{"getstrings_property", libaimdns_getstrings_property,
	    METH_VARARGS, libaimdns_getstrings_property_doc},
	{"getboolean_property", libaimdns_getboolean_property,
	    METH_VARARGS, libaimdns_getboolean_property_doc},
	{ "getinteger_property", libaimdns_getinteger_property,
	    METH_VARARGS, libaimdns_getinteger_property_doc},
	{"getifaddrs", libaimdns_getifaddrs,
	    METH_NOARGS, libaimdns_getifaddrs_doc},
	{NULL, NULL} /* Sentinel */
};

/*
 * initlibaimdns:
 *
 * Description:
 *   Initializes the Python extension libaimdns.
 *
 * Parameters:
 *   none
 *
 * Globals:
 *   libaiMDNSError - exception variable, modified
 *
 * Returns:
 *   none
 */
void
initlibaimdns()
{
	PyObject *module;

	/* initialize the libaimdns module */
	module = Py_InitModule("libaimdns", libaimdns_methods);
	if (module == NULL)
		return;

	/* setup the exception variable for libaimdns module */
	libaiMDNSError = PyErr_NewException("libaimdns.aiMDNSError", NULL,
	    NULL);
	PyModule_AddObject(module, "aiMDNSError", libaiMDNSError);
}
