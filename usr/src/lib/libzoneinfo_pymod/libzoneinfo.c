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

#include <Python.h>
#include <libzoneinfo.h>
#include <locale.h>

static PyObject *get_tz_info(PyObject *self, PyObject *args);
static PyObject *tz_isvalid(PyObject *self, PyObject *args);

/*
 * Create the method table that translates the method called
 * by the python program to the associated c function
 */
static PyMethodDef libzoneinfoMethods[] = {
	{"get_tz_info", (PyCFunction)get_tz_info, METH_VARARGS,
	"Get timezone information from libzoneinfo"},
	{"tz_isvalid", (PyCFunction)tz_isvalid, METH_VARARGS,
	"Check if timezone is valid per libzoneinfo"},
	{NULL, NULL, 0, NULL} };


PyMODINIT_FUNC
initlibzoneinfo(void)
{
	(void) Py_InitModule("libzoneinfo", libzoneinfoMethods);
}

/*
 * get_tz_info
 *
 * Description: Calls:
 *                  libzoneinfo:get_tz_continents,
 *                  libzoneinfo:get_tz_countries, and
 *                  libzoneinfo:get_timezones_by_country
 *              to obtain timezone information.
 * Parameters:
 *   arguments - pointer to a python object containing 0, 1, or 2 args.
 *               Number of args determines type of information returned
 *                   0 args - returns continent info
 *                   1 arg (ctnt_name) - returns country info
 *                   2 args (ctnt_name, ctry_code) - returns timezone info
 * Returns:
 *      On success: pylist of tuples, each tuple has three elements:
 *		tz_name: names of continent, country, or timezone
 *		tz_descr: descriptive name of continent, country,
 *                        or timezone
 *		tz_loc: localized name of continent, country,
 *                        or timezone
 *      On failure: empty pylist (or memory error if unable to create pylist)
 */
static PyObject *
get_tz_info(PyObject *self, PyObject *args)
{
	char *cont_name = NULL;
	char *cntry_name = NULL;
	struct	tz_continent *ctnts = NULL;
	struct tz_continent *pctnt = NULL;
	int nctnt;
	int i = 0;

	PyObject	*tz_tuple = NULL;
	PyObject	*tz_tuple_list = NULL;
	PyObject	*empty_list = NULL;

	if ((tz_tuple_list = PyList_New(0)) == NULL) {
	    return (PyErr_NoMemory());
	}

	if ((empty_list = PyList_New(0)) == NULL) {
	    return (PyErr_NoMemory());
	}

	/*
	 * Can be called with 0, 1, or 2 args
	 *   0 args - returns continent info
	 *   1 arg (ctnt_name) - returns country info
	 *   2 args (ctnt_name, ctry_code) - returns timezone info
	 */
	if (!PyArg_ParseTuple(args, "|zz", &cont_name, &cntry_name)) {
		return (Py_BuildValue("O", empty_list));
	}

	/*
	 * Pickup locale
	 */
	setlocale(LC_MESSAGES, "");

	/*
	 * Make library call
	 */
	nctnt = get_tz_continents(&ctnts);
	if (nctnt == -1) {
		return (Py_BuildValue("O", empty_list));
	}

	for (i = 1, pctnt = ctnts; pctnt != NULL;
			pctnt = pctnt->ctnt_next, i++) {
		PyObject *item_name = NULL;
		PyObject *item_desc = NULL;
		PyObject *item_loc = NULL;
		char *curcont = NULL;
		int nctry;
		int j;
		struct tz_country *cntries;
		struct tz_country *pctry;

		if (cont_name == NULL) {
			/*
			 * Create list of continent tuples, each with:
			 *	continent name
			 *	continent name descriptive
			 *	localized continent name
			 */
			if ((tz_tuple = PyTuple_New(3)) == NULL) {
				return (Py_BuildValue("O", empty_list));
			}

			/*
			 * Need to get continent list
			 */
			item_name = PyString_FromString(pctnt->ctnt_name);
			if (pctnt->ctnt_id_desc != NULL) {
				item_desc = PyString_FromString(
				    pctnt->ctnt_id_desc);
			} else {
				item_desc = PyString_FromString("");
			}

			if (pctnt->ctnt_display_desc != NULL) {
				item_loc = PyString_FromString(
				    pctnt->ctnt_display_desc);
			} else {
				item_loc = PyString_FromString("");
			}

			PyTuple_SetItem(tz_tuple, 0, item_name);
			PyTuple_SetItem(tz_tuple, 1, item_desc);
			PyTuple_SetItem(tz_tuple, 2, item_loc);
			if (PyList_Append(tz_tuple_list, tz_tuple) != 0) {
				return (Py_BuildValue("O", empty_list));
			}
			Py_DECREF(tz_tuple);
			continue;
		}

		/*
		 * Name of continent passed in. Look for match.
		 */
		curcont = pctnt->ctnt_name;
		if (strncmp(curcont, cont_name, strlen(cont_name)) != 0) {
			continue;
		}

		/*
		 * Found matching continent. Now get its countries.
		 */
		nctry = get_tz_countries(&cntries, pctnt);
		if (nctry == -1) {
			return (Py_BuildValue("O", empty_list));
		}
		for (j = 1, pctry = cntries; pctry != NULL;
				pctry = pctry->ctry_next, j++) {
			struct tz_timezone *tzs;
			struct tz_timezone *ptz;
			char *cur_country = NULL;
			int ntz;
			int k;

			/*
			 * Create list of country tuples, each with:
			 *	country name/id
			 *	country name descriptive
			 *	localized country name
			 */
			if (cntry_name == NULL) {
				if ((tz_tuple = PyTuple_New(3)) == NULL) {
					return (Py_BuildValue("O", empty_list));
				}
				item_name = PyString_FromString(
				    pctry->ctry_code);
				if (pctry->ctry_id_desc != NULL) {
					item_desc = PyString_FromString(
					    pctry->ctry_id_desc);
				} else {
					item_desc = PyString_FromString("");
				}
				if (pctry->ctry_display_desc != NULL) {
					item_loc = PyString_FromString(
					    pctry->ctry_display_desc);
				} else {
					item_loc = PyString_FromString("");
				}

				PyTuple_SetItem(tz_tuple, 0, item_name);
				PyTuple_SetItem(tz_tuple, 1, item_desc);
				PyTuple_SetItem(tz_tuple, 2, item_loc);
				if (PyList_Append(tz_tuple_list,
				    tz_tuple) != 0) {
					return (Py_BuildValue("O", empty_list));
				}
				Py_DECREF(tz_tuple);
				continue;
			}

			/*
			 * Name of country passed in. Look for match.
			 */
			cur_country = pctry->ctry_code;
			if (strncmp(cur_country, cntry_name,
			    strlen(cntry_name)) != 0) {
				continue;
			}

			/*
			 *  Found matching country. Now get its timezones.
			 */
			ntz = get_timezones_by_country(&tzs, pctry);

			for (k = 1, ptz = tzs; ptz != NULL;
			    ptz = ptz->tz_next) {
				/*
				 * Create list of timezone tuples, each with:
				 *	timezone name
				 *	timezone name descriptive
				 *	localized timezone name
				 *	tz_loc: localized timezone names
				 */
				if ((tz_tuple = PyTuple_New(3)) == NULL) {
					return (Py_BuildValue("O", empty_list));
				}
				item_name = PyString_FromString(ptz->tz_name);
				if (ptz->tz_id_desc != NULL) {
					item_desc = PyString_FromString(
					    ptz->tz_id_desc);
				} else {
					item_desc = PyString_FromString("");
				}
				if (ptz->tz_display_desc != NULL) {
					item_loc = PyString_FromString(
					    ptz->tz_display_desc);
				} else {
					item_loc = PyString_FromString("");
				}

				PyTuple_SetItem(tz_tuple, 0, item_name);
				PyTuple_SetItem(tz_tuple, 1, item_desc);
				PyTuple_SetItem(tz_tuple, 2, item_loc);
				if (PyList_Append(tz_tuple_list,
				    tz_tuple) != 0) {
					return (Py_BuildValue("O", empty_list));
				}
				Py_DECREF(tz_tuple);
			}
			(void) free_timezones(tzs);
			break;
		}
		(void) free_tz_countries(cntries);
		break;
	}

	(void) free_tz_continents(ctnts);
	return (Py_BuildValue("O", tz_tuple_list));
}


/*
 * tz_isvalid
 *
 * Description: Calls:
 *                  libzoneinfo:isvalid_tz
 *              to check if timezone is valid.
 * Parameters:
 *   arguments - pointer to a python object containing name of timezone
 *		 to be checked for validity
 * Returns:
 *      1, if timezone is valid per libzoneinfo:isvalid_tz
 */
static PyObject *
tz_isvalid(PyObject *self, PyObject *args)
{
	char *timezone = NULL;

	if (!PyArg_ParseTuple(args, "s", &timezone)) {
		return (Py_BuildValue("i", 2));
	}

	return (Py_BuildValue("i", isvalid_tz(timezone, "/", _VTZ_ZONEINFO)));
}
