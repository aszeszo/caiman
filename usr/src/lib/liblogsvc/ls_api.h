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
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _LS_API_H
#define	_LS_API_H

#pragma ident	"@(#)ls_api.h	1.1	07/08/03 SMI"

/*
 * This header file is for users of the Debugging/Logging library
 */

#ifdef __cplusplus
extern "C" {
#endif

/* type definitions */

/* error codes */

typedef enum {
	LS_E_SUCCESS = 0,	/* command succeeded */
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
	LS_DBGLVL_TRACE,
	LS_DBGLVL_LAST	/* serves only as end mark of the list */
} ls_dbglvl_t;

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
void ls_init_log(void);

/* initialize debugging service */
void ls_init_dbg(void);

/* set debugging level */
ls_errno_t ls_set_dbg_level(ls_dbglvl_t level);

/* obtain current debugging level */
ls_dbglvl_t ls_get_dbg_level(void);

/* register alternate logging method performing actual logging action */
void ls_register_log_method(ls_log_method_t func);

/* register alternate method performing actual posting of debug message */
void ls_register_dbg_method(ls_dbg_method_t func);

/* post log message */
/* PRINTFLIKE2 */
void ls_write_log_message(const char *id, const char *fmt, ...);

/* post debug message */
/* PRINTFLIKE3 */
void ls_write_dbg_message(const char *id, ls_dbglvl_t level,
    const char *fmt, ...);

#ifdef __cplusplus
}
#endif

#endif /* _LS_API_H */
