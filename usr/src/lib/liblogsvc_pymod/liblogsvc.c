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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#include <Python.h>
#include "ls_api.h"

/*
 * public logsvc functions
 */

static PyObject *write_log_message(PyObject *, PyObject *);
static PyObject *write_dbg_message(PyObject *, PyObject *);
void initliblogsvc();

/* Private python initialization structure */

static struct PyMethodDef liblogsvcMethods[] = {
	{"write_log", write_log_message, METH_VARARGS,
	    "Write to logfile"},
	{"write_dbg", write_dbg_message, METH_VARARGS,
	    "Write to debg logfile"},
	{NULL, NULL, 0, NULL}
};

/*
 * write_log_message - Python-callable wrapper for ls_write_log_message
 * parameters:
 *      id - log module identification
 *      buf - character string - must already be formatted
 * returns NULL if argument parsing error, 1 otherwise
 * must be loaded with call to ls_init_python_module()
 * declared static - callable only by Python through table
 */
static PyObject *
write_log_message(PyObject *self, PyObject *args)
{
	char    buf[LS_MESSAGE_MAXLEN + LS_ID_MAXLEN + 1];
        char    *id, *msg;

        if (!PyArg_ParseTuple(args, "ss", &id, &msg))
        	return (Py_BuildValue("i", 0));

	(void) strlcpy(buf, msg, sizeof (buf));
	ls_write_log_message(id, buf);
        return (Py_BuildValue("i", 1));
}

/*
 * write_dbg_message - Python-callable wrapper for ls_write_dbg_message
 * parameters:
 *      id - log module identification
 *      level - debugging level
 *      buf - character string - must already be formatted
 * returns NULL if argument parsing error, 1 otherwise
 * must be loaded with call to ls_init_python_module()
 * declared static - callable only by Python through table
 */
static PyObject *
write_dbg_message(PyObject *self, PyObject *args)
{
	char    buf[LS_MESSAGE_MAXLEN + LS_ID_MAXLEN + 1];
        char    *id, *msg;
        int     level;

        if (!PyArg_ParseTuple(args, "sis", &id, &level, &msg))
        	return (Py_BuildValue("i", 0));

        /* only post message, if current debugging level allows it */

        if (level <= ls_get_dbg_level()) {
                (void) strlcpy(buf, msg, sizeof (buf));
                ls_write_dbg_message(id, level, buf);
        }
        return (Py_BuildValue("i", 1));
}

void
initliblogsvc()
{
	PyObject	*mod;

	/* initialize module and its methods */
	/* PyMODINIT_FUNC; */
	mod = Py_InitModule("liblogsvc", liblogsvcMethods);
	
	/* initialize constants in module */
	/* debugging levels */
        PyModule_AddIntConstant(mod, "LS_DBGLVL_NONE", LS_DBGLVL_NONE);
        PyModule_AddIntConstant(mod, "LS_DBGLVL_EMERG", LS_DBGLVL_EMERG);
        PyModule_AddIntConstant(mod, "LS_DBGLVL_ERR", LS_DBGLVL_ERR);
        PyModule_AddIntConstant(mod, "LS_DBGLVL_WARN", LS_DBGLVL_WARN);
        PyModule_AddIntConstant(mod, "LS_DBGLVL_INFO", LS_DBGLVL_INFO);
        /* destinations */
        PyModule_AddIntConstant(mod, "LS_DEST_NONE", LS_DEST_NONE);
        PyModule_AddIntConstant(mod, "LS_DEST_CONSOLE", LS_DEST_CONSOLE);
        PyModule_AddIntConstant(mod, "LS_DEST_FILE", LS_DEST_FILE);
}
