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

#ifndef _LS_API_H
#define	_LS_API_H

/*
 * This header file is for users of the Debugging/Logging library
 */

#include <libnvpair.h>

#ifdef __cplusplus
extern "C" {
#endif

/* type definitions */

/* error codes */

typedef enum {
	LS_E_SUCCESS = 0,	/* command succeeded */
	LS_E_NOMEM,		/* memory allocation failed */
	LS_E_LOG_TRANSFER_FAILED,	/* couldn't transfer log file */
	LS_E_INVAL = -1		/* input parameter invalid */
} ls_errno_t;

/* destination for generated messages */

typedef enum {
	LS_DEST_NONE = 0,
	LS_DEST_CONSOLE = 0x01,
	LS_DEST_FILE = 0x02
} ls_dest_t;

/* debugging levels */

typedef enum {
	LS_DBGLVL_NONE = 0,
	LS_DBGLVL_EMERG,
	LS_DBGLVL_ERR,
	LS_DBGLVL_WARN,
	LS_DBGLVL_INFO,
	LS_DBGLVL_LAST	/* serves only as end mark of the list */
} ls_dbglvl_t;

/*
 * select either stdout, stderr, or both
 */
typedef enum {
	LS_STDOUT,
	LS_STDERR,
	LS_STDOUTERR
} ls_stdouterr_t;

/* constants */

/* max length of log/debug message */
#define	LS_MESSAGE_MAXLEN	1000

/* max length of ID string */
#define	LS_ID_MAXLEN		50

/* post messages both to console and file */
#define	LS_DEST_BOTH (LS_DEST_CONSOLE | LS_DEST_FILE)

/* logging method */
typedef void (*ls_log_method_t)(const char *id, char *msg);

/* debugging method */
typedef void (*ls_dbg_method_t)(const char *id, ls_dbglvl_t level, char *msg);

/* function prototypes */

/* initialize logging service */
ls_errno_t ls_init(nvlist_t *params);

/* transfer log file */
ls_errno_t ls_transfer(char *src_mountpoint, char *dst_mountpoint);

/* set debugging level */
ls_errno_t ls_set_dbg_level(ls_dbglvl_t level);

/* obtain current debugging level */
ls_dbglvl_t ls_get_dbg_level(void);

/* register alternate logging method performing actual logging action */
void ls_register_log_method(ls_log_method_t func);

/* register alternate method performing actual posting of debug message */
void ls_register_dbg_method(ls_dbg_method_t func);

/* nvlist attributes for customizing logging service */

/* log file */
#define	LS_ATTR_LOG_FILE	"ls_log_file"

/* debug level */
#define	LS_ATTR_DBG_LVL		"ls_dbg_lvl"

/* destination */
#define	LS_ATTR_DEST		"ls_dest"

/* timestamp */
#define	LS_ATTR_TIMESTAMP	"ls_timestamp"

/* destination log file path */
#define	LS_LOGFILE_DST_PATH	"/var/sadm/system/logs/"


/* post log message */
/* PRINTFLIKE2 */
void ls_write_log_message(const char *id, const char *fmt, ...);

/* post debug message */
/* PRINTFLIKE3 */
void ls_write_dbg_message(const char *id, ls_dbglvl_t level,
    const char *fmt, ...);

/*
 * log to either stdout, stderr, or both, logfile
 */
void ls_log_std(ls_stdouterr_t, const char *id, char *buf);

/* initialize Python module logsvc */
boolean_t ls_init_python_module(void);

#ifdef __cplusplus
}
#endif

#endif /* _LS_API_H */
