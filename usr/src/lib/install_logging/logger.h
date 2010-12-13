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
 *
 * Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
 *
 */

#ifndef _INSTALL_LOGGING_H
#define _INSTALL_LOGGING_H

#include <Python.h>
#include <string.h>
#include <sys/types.h>
#include <sys/varargs.h>
#include <stdlib.h>
#include <libnvpair.h>
#include <liberrsvc.h>

#define	NVATTRS	NV_UNIQUE_NAME | NV_UNIQUE_NAME_TYPE

typedef void *logger_t;

/* Logging Levels */
#define CRITICAL "critical"
#define FATAL "fatal"
#define ERROR "error"
#define WARNING "warning"
#define INFO "info"
#define DEBUG "debug"
#define NOTSET  "NOTSET"

/* Logging handler identifiers */
typedef enum {
        LOGGING_FILE_HDLR,              /* Handler is a FileHandler */
        LOGGING_PROGRESS_HDLR,          /* Handler is a ProgressHandler */
        LOGGING_STREAM_HDLR,            /* Handler is a StreamHandler */
        LOGGING_HTTP_HDLR               /* Handler is an HTTPHandler */
} logging_handler_type_t;

typedef void *logger_handler_t;

/* Handlers used by consumers of logging */
#define	HANDLER			"handler"
#define	FILE_HANDLER		"FileHandler"
#define	PROGRESS_HANDLER	"ProgressHandler"
#define	HTTP_HANDLER		"HTTPHandler"
#define	STREAM_HANDLER		"StreamHandler"


/* Attributes used by handlers */
#define	FILENAME	"filename"
#define	MODE		"mode"
#define	LEVEL		"level"
#define	PORT		"port"
#define	HOST		"host"
#define	URL		"url"
#define	METHOD		"method"
#define	STRM		"strm"
#define	PROGRESS	"progress"
#define	MESSAGE		"msg"

/* Attributes used to transfer logs */
#define SOURCE          "source"
#define DEST            "destination"

/* Attributes used to construct a list of log files */
typedef struct log_file_list {
	char *logfile;
	struct log_file_list *logfile_next;
} log_file_list_t;

/*
 * Public interface functions
 */
boolean_t set_logger_class(const char *);
boolean_t transfer_log(logger_t *,  nvlist_t *);
boolean_t set_log_level(logger_t *, char *);
boolean_t add_handler(logger_t *, nvlist_t *, logging_handler_type_t hdlrtyp);
boolean_t log_message(logger_t *, const char *, const char *, ...);
logger_t *get_logger(const char *);
boolean_t report_progress(logger_t *, long, const char *, ...);
log_file_list_t *close_logging(logger_t *); 
/* Parameters for reporting errors */
extern char		*LOG_MOD_ID;

/* function for reporting errors to the errsvc */
extern void _report_error(int, char *, char *, ...);


/* Error codes for install_logging */
#define	LOGGING_ERR_PY_INIT		1	/* Initializing Python module failed */
#define	LOGGING_ERR_DATA_INVALID	2	/* The data is invalid */
#define	LOGGING_ERR_PY_FUNC		3	/* A Python error occurred */
#define LOGGING_ERR_REPORTING_ERROR	4	/* A failure reporting the error occurred */ 

#endif  /* _INSTALL_LOGGING_H */
