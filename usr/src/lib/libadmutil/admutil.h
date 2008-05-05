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
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _ADMUTIL_H
#define	_ADMUTIL_H


#ifdef __cplusplus
extern "C" {
#endif

/*
 * NIS+ host cred defs
 */
#define	NISPLUS_DES	"DES"
#define	DEF_PASSWORD	"nisplus"

int
modify_timezone(char *clientname, char *clientroot, char *timezone);

/*
 * General extern defs.
 */
extern void remove_component(char *);
extern char *basename(char *);
extern char *tempfile(const char *);
extern int trav_link(char **);
extern int lock_db(char *, int, int *);
extern int unlock_db(int *);

extern int set_timezone(char *, char *);
extern int get_nodename(char *, char *);
extern int set_nodename(char *, int);
extern int get_domain(char *, char *, char *);
extern int set_domain(char *, int);
extern int config_nsprofile(char *);
extern int config_alt_nsprofile(char *, char *);
extern int config_nsswitch(char *);
extern int config_alt_nsswitch(char *, char *);
extern int config_resolv(char *, char **, int, char **, int, char **, int,
	char **, int);
extern int get_net_if_ip_netmask(char *, char *);
extern int set_net_if_ip_netmask(char *, char *);
extern int get_net_if_ip_addr(char *, char *);
extern int set_net_if_status(char *, char *, char *, char *, char *);
/* most files don't include net/if.h, so struct ifconf is not defined */
/* extern int get_net_if_names(struct ifconf *); */
/* extern int get_net_lif_names(struct lifconf *); */
extern int set_run_level(char *);
extern int is_local_host(char *);
extern int config_krb(char **kin);
extern int config_nfs4(int, const char *, char *);
extern int unconfig_nfs4(const char *, char *);

/* control flags for some of the functions */

#define	TE_NOW_BIT	1
#define	TE_BOOT_BIT	2
#define	TE_NOWANDBOOT_BITS	(TE_NOW_BIT | TE_BOOT_BIT)

/* config_nsswitch */

#define	TEMPLATE_FILES		"/etc/nsswitch.files"
#define	TEMPLATE_NIS		"/etc/nsswitch.nis"
#define	TEMPLATE_NIS_PLUS	"/etc/nsswitch.nisplus"
#define	TEMPLATE_DNS		"/etc/nsswitch.dns"

/* config_nsprofile */

#define	NSPROFILE_DIR			"/var/svc/profile"
#define	NSPROFILE_TEMPLATE_FILES	"/var/svc/profile/ns_files.xml"
#define	NSPROFILE_TEMPLATE_NIS		"/var/svc/profile/ns_nis.xml"
#define	NSPROFILE_TEMPLATE_NIS_PLUS	"/var/svc/profile/ns_nisplus.xml"
#define	NSPROFILE_TEMPLATE_DNS		"/var/svc/profile/ns_dns.xml"
#define	NSPROFILE_TEMPLATE_LDAP		"/var/svc/profile/ns_ldap.xml"
#define	FILES_NSPROFILE_TEMPLATE	"ns_files.xml"

#define	ADMUTIL_UP	"up"
#define	ADMUTIL_DOWN	"down"
#define	ADMUTIL_YES	"yes"
#define	ADMUTIL_NO	"no"

/* config_nfs4 */

#define	NFS4CFG_FILE		"/etc/default/nfs"

#ifndef	NFS4CMD_CONFIG
#define	NFS4CMD_CONFIG		0
#define	NFS4CMD_UNCONFIG	1
#define	NFS4CMD_COMMENT		2
#define	NFS4CMD_UNCOMMENT	3
#endif

/*
 * Return codes for utility functions.
 * These functions all return 0 if they ran ok.  They return >0 if there
 * was a system problem.  The return code in this case is the errno.  They
 * return < 0 if there was an internal failure in the function.  The following
 * defines represent the failures in this case.
 */

/* set_timezone */
#define	ADMUTIL_SETTZ_BAD -1		/* invalid timezone */
#define	ADMUTIL_SETTZ_RTC -2		/* rtc failed */

/* get_nodename */
#define	ADMUTIL_GETNN_SYS -1		/* sysinfo failed */

/* set_nodename */
#define	ADMUTIL_SETNN_BAD -1		/* invalid nodename */
#define	ADMUTIL_SETNN_SYS -2		/* sysinfo failed */

/* get_domain */
#define	ADMUTIL_GETDM_SYS -1		/* sysinfo failed */

/* set_domain */
#define	ADMUTIL_SETDM_BAD -1		/* invalid domainname */
#define	ADMUTIL_SETDM_SYS -2		/* sysinfo failed */

/* config_nsswitch */
#define	ADMUTIL_SWITCH_STAT -3		/* stat nsswitch */
#define	ADMUTIL_SWITCH_TOPEN -4		/* temp file open */
#define	ADMUTIL_SWITCH_OPEN -5		/* work file open */
#define	ADMUTIL_SWITCH_WCHMOD -6	/* work file chmod */
#define	ADMUTIL_SWITCH_WCHOWN -7	/* work file chown */
#define	ADMUTIL_SWITCH_READ -8		/* nsswitch file read */
#define	ADMUTIL_SWITCH_WRITE -9		/* tempfile write */

/* config_nsprofile */
#define	ADMUTIL_NSPROFILE_STRLCPY -3	/* strlcpy name_service.xml */
#define	ADMUTIL_NSPROFILE_UNLINK -4	/* unlink name_service.xml */
#define	ADMUTIL_NSPROFILE_SYMLINK -5	/* symlink name_service.xml */
#define	ADMUTIL_NSPROFILE_NO_PROFILE_DIR -6	/* no nsprofile dir */

/* config_resolv */
#define	ADMUTIL_RESOLV_STAT -3		/* stat resolv.conf */
#define	ADMUTIL_RESOLV_WRITE -7		/* work file write */

/* set_net_if_ip_netmask */
#define	ADMUTIL_SETMASK_BAD -1		/* invalid netmask */
#define	ADMUTIL_SETMASK_SOCK -2		/* socket */
#define	ADMUTIL_SETMASK_IOCTL -3	/* ioctl */

/* get_net_if_ip_netmask */
#define	ADMUTIL_GETMASK_BAD		-1		/* invalid netmask */
#define	ADMUTIL_GETMASK_SOCK	-2		/* socket */
#define	ADMUTIL_GETMASK_IOCTL	-3		/* ioctl */

/* get_net_if_ip_addr */
#define	ADMUTIL_GETIP_SOCK -1		/* socket */
#define	ADMUTIL_GETIP_IOCTL -2		/* ioctl */

/* set_net_if_status */
#define	ADMUTIL_SETIFS_SOCK -1		/* socket */
#define	ADMUTIL_SETIFS_IOCTL -2		/* ioctl */

/* get_net_if_names */
#define	ADMUTIL_GETIFN_SOCK -1		/* socket */
#define	ADMUTIL_GETIFN_IOCTL -2		/* ioctl */
#define	ADMUTIL_GETIFN_MEM -3		/* malloc */

/* config_nfs4 */
#define	ADMUTIL_NFS4_CFG_STAT		-1 /* error stating /etc/default/nfs */
#define	ADMUTIL_NFS4_CFG_OPEN_RO	-2 /* error opening nfs4 cfg file RO */
#define	ADMUTIL_NFS4_CFG_OPEN_RW	-3 /* error opening nfs4 cfg file RW */
#define	ADMUTIL_NFS4_CFG_CREAT		-4 /* error creating nfs4 cfg file   */
#define	ADMUTIL_NFS4_CFG_FDOPEN		-5 /* error assoc. stream to nfs4 fd */
#define	ADMUTIL_NFS4_WRK_OPEN		-6 /* error opening work file	*/
#define	ADMUTIL_NFS4_WRK_FDOPEN		-7 /* error assoc. stream to work fd */
#define	ADMUTIL_NFS4_WCHMOD		-8 /* error on chmod of work file    */
#define	ADMUTIL_NFS4_WCHOWN		-9 /* error on chown of work file    */

/* unconfig_files */
#define	ADMUTIL_UNCONF_TZ	-1	/* timezone */
#define	ADMUTIL_UNCONF_COLD	-2	/* unlink coldstart */
#define	ADMUTIL_UNCONF_DOM	-3	/* get_domain */
#define	ADMUTIL_UNCONF_YP	-4	/* yp cleanup */
#define	ADMUTIL_UNCONF_NS	-5	/* nsswitch */
#define	ADMUTIL_UNCONF_DFD	-6	/* defaultdomain */
#define	ADMUTIL_UNCONF_DFR	-7	/* default router */
#define	ADMUTIL_UNCONF_NTM	-8	/* netmasks */
#define	ADMUTIL_UNCONF_NN	-9	/* nodename */
#define	ADMUTIL_UNCONF_SI	-10	/* sysinfo */
#define	ADMUTIL_UNCONF_SH	-12	/* save hosts file */
#define	ADMUTIL_UNCONF_IF	-13	/* get_net_if_names */
#define	ADMUTIL_UNCONF_OP	-14	/* open */
#define	ADMUTIL_UNCONF_PW	-15	/* passwd */
#define	ADMUTIL_UNCONF_HF	-16	/* hosts files */
#define	ADMUTIL_UNCONF_RC	-17	/* resolv.conf */
#define	ADMUTIL_UNCONF_KRB	-19	/* krb5.conf */
#define	ADMUTIL_UNCONF_RK -20		/* sysid configuration file */
#define	ADMUTIL_UNCONF_PF -21		/* sysid configuration file */
#define	ADMUTIL_UNCONF_LDCA -22		/* ldap client cache */
#define	ADMUTIL_UNCONF_LDCR -23		/* ldap client cred */
#define	ADMUTIL_UNCONF_LDF -24		/* ldap client file */
#define	ADMUTIL_UNCONF_LDLG -25		/* ldap cache log */
#define	ADMUTIL_UNCONF_RTC -26		/* rtc config file */
#define	ADMUTIL_UNCONF_MLC	-27	/* malloc failure */
#define	ADMUTIL_UNCONF_DA	-28	/* dumpadm */
#define	ADMUTIL_UNCONF_SSH	-29	/* ssh host keys */
#define	ADMUTIL_UNCONF_NSPROFILE -30	/* nsprofile */
#define	ADMUTIL_UNCONF_AGGR	-31	/* aggregations */

/* util */
#define	ADMUTIL_UTIL_LINK	-100	/* trav_link */
#define	ADMUTIL_UTIL_WORK	-101	/* work file */
#define	ADMUTIL_UTIL_OPEN	-103	/* work file open */
#define	ADMUTIL_UTIL_WCHMOD	-104	/* work file chmod */
#define	ADMUTIL_UTIL_WCHOWN	-105	/* work file chown */
#define	ADMUTIL_UTIL_REN	-106	/* work file rename */

#ifdef __cplusplus
}
#endif

#endif /* _ADMUTIL_H */
