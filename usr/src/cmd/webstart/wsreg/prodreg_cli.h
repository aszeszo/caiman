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

/*
 * prodreg_cli.h
 *
 * These definitions are used internally by the prodreg CLI implementation.
 * They are not intended to be exported beyond the current implementation.
 */

#ifndef	_PRODREG_CLI_H_
#define	_PRODREG_CLI_H_


#ifdef __cplusplus
extern "C" {
#endif

#define	PRODREG_GUI	"/usr/dt/bin/sdtprodreg"

/*
 * Note:  The inclusion of localized_strings.h follows that of the
 *        definition of PRODREG_GUI since this definition is used
 *        in localized_strings.h
 */
#include "localized_strings.h"

#define	ALTERNATE_ROOT_VARIABLE	"PKG_INSTALL_ROOT"


#define	DEBUGINFO	__FILE__, __LINE__
#define	CHK(a)		((a) != NULL) ? (a) : ""

typedef enum {
	CMD_UNKNOWN = 0, CMD_AWT = 1, CMD_BROWSE, CMD_HELP, CMD_INFO,
	CMD_SWING, CMD_UNINSTALL, CMD_UNREGISTER, CMD_REGISTER,
	CMD_VERSION, ALT_ROOT, CMD_LIST
} cmd_code;

/* From prodreg_browse_num.c */
extern uint32_t get_bn(char *pcuuid);
extern void db_open(void);
extern void db_close(void);
extern char * getUUIDbyBrowseNum(uint32_t ul);

/*
 * From prodreg_browse.c
 *
 * Possible combinations: FIND_UUID [(FIND_LOCN|FIND_INST)] | FIND_NAME
 * These are the values which can be set for Criteria.mask.  They are set
 * by the command line flags, and checked before passing to the search
 * routines.
 */

#define	FIND_UUID	1
#define	FIND_LOCN	2
#define	FIND_INST	4
#define	FIND_NAME	8
#define	FIND_UNAME	16

typedef struct criteria {
	const char *uuid;
	const char *location;
	const char *displayname;
	const char *uniquename;
	int	instance;
	int	mask;
} Criteria;

#define	ROOT_UUID "root"
#define	SYSS_UUID "a01ee8dd-1dd1-11b2-a3f2-0800209a5b6b"
#define	ADDL_UUID "b1c43601-1dd1-11b2-a3f2-0800209a5b6b"
#define	LOCL_UUID "a8dcab4f-1dd1-11b2-a3f2-0800209a5b6b"
#define	SYSL_UUID "b96ae9a9-1dd1-11b2-a3f2-0800209a5b6b"
#define	UNCL_UUID "8f64eabf-1dd2-11b2-a3f1-0800209a5b6b"

#define	ROOT_STR  "System Registry"
#define	SYSS_STR  "Solaris %s System Software"
#define	ADDL_STR  "Additional System Software"

#define	SYSL_STR  "System Software Localizations"
#define	LOCL_STR  "Software Localizations"
#define	UNCL_STR  "Unclassified Software"
#define	ENTR_STR  "Entire Software Distribution"

#define	CFILL(c, u, l, d, i, m) { (c).uuid = (u); (c).location = (l); \
	(c).displayname = (d); (c).instance = (i); (c).mask = (m); }

/*
 * SPECIALROOT checks to see if criteria matches a given uuid and string
 *    c   The criteria
 *    u   The UUID
 *    s   The string, a display name.
 */
#define	SPECIALROOT(c, u, s) \
((((c).mask & FIND_UUID) && (c).uuid && 0 == strcmp((c).uuid, u)) || \
(((c).mask & FIND_NAME) && (c).displayname && \
0 == strcmp((c).displayname, s)))

/*
 * RootType is used as a search result, to provide the display routine
 * with information about the status of the component that has been
 * found.
 */
typedef enum {
	ENTIRE = 1,	/* Component is ancestor of 'entire distribution'. */
	ADDL = 2,	/* '' is an ancestor of 'additional software.' */
	LOCL = 3,	/* '' is an ancestor of 'localization software.' */
	UNCL = 4,	/* '' is an ancestor of 'unclassified software.' */
	AMBIG = 5,	/* '' is ambiguous in tree.  Show choices only. */
	ROOT = 6,	/* '' is an ancestor of root. */
	SYSS = 7,	/* '' is an ancestor of system software */
	SYSL = 8,	/* '' is an ancestor of system localization software */
	NONE = 9	/* '' is not in the tree.  Show nothing. */
} RootType;

/* These definitions are used as the first parameter to show() */
#define	NODE	1
#define	CHILD	2
#define	PARENT	3

extern void browse_request(const char *, Criteria);
extern void progress(int);

/* From prodreg_uninst.c */
extern void prodreg_uninstall(char **, const char *, Criteria, int);

/* From prodreg_util.c */

extern void fail(const char *);
extern void debug(char *, int, const char *, ...);
extern Wsreg_component * prodreg_get_component(const char *, Criteria,
    int, Wsreg_component ***, Wsreg_component ***);
extern void fill_in_comps(Wsreg_component **, Wsreg_component **);
extern void fill_in_comp(Wsreg_component *, Wsreg_component **);
extern void pretty_comp(const Wsreg_component *);
extern void check_dependent(int, int, Wsreg_component *, const char *);
extern void launch_installer(const char *, char **);
extern int search_sys_pkgs(Wsreg_component **ppws_sysp,
    Wsreg_component ***pppws_parent, Wsreg_component ***pppws_children,
    Wsreg_component ***pppws_ambig, Wsreg_component **ppws,
    RootType *proot, Criteria criteria);
extern void browse_header(void);
extern void show(int, int, int, uint32_t, const char *, int, const char *);
extern int okpkg(const char *, const char *, char **);
extern char * nextstr(int *, const char *);
extern char * getval(const char *, const char *);

#ifndef NDEBUG
extern char * make_arglist(int, int, char **);
#endif

/* This is the increment to grow dynamic arrays. */
#define	DYNA_INCR 10
extern void resize_if_needed(int, int *, Wsreg_component ***, int);

/* From prodreg_info.c */
extern void prodreg_info(const char *, Criteria, const char *, int);

/* From prodreg_unreg.c */
extern void prodreg_unregister(const char *, Criteria, int, int);

/* From prodreg_reg.c */
extern void prodreg_register(const char *, char *, char *,
    char *[], char *[], char *[], char *[], char *[], char *[],
    char *, char *, char *, char *, char *, char *);

/* From prodreg_list.c */
extern void prodreg_list(char *, int, char *[]);

/* From prodreg.c */
extern char *global_lang;
extern char *global_solver;
extern char *global_ENTR_UUID;

/* private CLI api from wsreg.c */
extern int	_private_wsreg_register(Wsreg_component *);
extern int	_private_wsreg_unregister(const Wsreg_component *);
extern int	_private_wsreg_can_access_registry(int mode);

#ifdef __cplusplus
}
#endif

#endif	/* _PRODREG_CLI_H_ */
