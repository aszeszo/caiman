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
 * Copyright 2000 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)etheraddr.c	1.5	06/02/27 SMI"

#include "etheraddr.h"
#include <stdlib.h> /* For malloc & friends */
#include <stdio.h> /* For printf, etc */
#include <fcntl.h> /* For O_RDWR */
#include <string.h> /* For strchr, etc */
#include <libdevinfo.h> /* Various device ops */
#include <stropts.h> /* For stream ops (put/getmsg, etc) */
#include <sys/sockio.h> /* for put/getmsg */
#include <assert.h>
/*
 * debugging flag
 */
static	int	debug = 0;


/* Timeout for DLPI acks */
static	int	dlpi_timeout = DLPI_TIMEOUT;

/*
 * Global functions
 */
int	dlpi_get_address(char *, struct ether_addr *);
int	get_net_if_names(char ***);
void	free_net_if_names(char **);


/*
 * local functions
 */
static	int	dlpi_info_req(int, dl_info_ack_t *);
static	int	timed_getmsg(int, struct strbuf *, int *, int, char *, char *);
static	int	ifrm_num(char *, unsigned int *);
static	int	open_dev(dev_att_t *, int, int *, int);
static	void	pf_dev_att(dev_att_t *);
static	void	parse_ifname(dev_att_t *);
static	int	ifname_open(char *, dev_att_t *);
static	int	dlpi_open_attach(char *);
static	int	dlpi_attach(int, int, int);
static	int	dlpi_get_phys(int, uchar_t *);
static	int	dlpi_info_req(int, dl_info_ack_t *);
static	int	timed_getmsg(int, struct strbuf *, int *, int, char *, char *);


/* Get all interface names.  This will include IPv6 names. */
int
get_net_if_names(char ***names)
{
	char *buf;		/* buffer for socket info */
	int sd;			/* socket descriptor */
	int ifn;	/* interface count structure */
	struct ifconf ifc;    /* interface config buffer */
	struct ifreq *ifrp;
	int numifs;
	char **tmpnames;
	int cnt;
	int n;
	char *tmpname;
	sd = socket(AF_INET, SOCK_DGRAM, 0);
	if (sd < 0)
		return (-1);

	if (ioctl(sd, SIOCGIFNUM, &ifn) < 0) {
		(void) close(sd);
		return (-1);
	}

	if (!(buf = (char *)malloc(ifn * sizeof (struct ifreq)))) {
		(void) close(sd);
		return (-1);
	}

	ifc.ifc_len = ifn * sizeof (struct ifreq);
	ifc.ifc_buf = (caddr_t)buf;
	if (ioctl(sd, SIOCGIFCONF, (char *)&ifc) < 0) {
		(void) close(sd);
		return (-1);
	}

	(void) close(sd);


	ifrp = ifc.ifc_req;
	numifs = ifc.ifc_len / sizeof (struct ifreq);
	tmpnames = (char **)malloc((numifs+1) * sizeof (char *));
	cnt = 0;
	for (n = 0; n < numifs; n++, ifrp++) {
		tmpname =
		    (char *)malloc((strlen(ifrp->ifr_name)+1) *
			sizeof (char));
		(void) memcpy(tmpname, ifrp->ifr_name, strlen(ifrp->ifr_name));
		tmpname[strlen(ifrp->ifr_name)] = '\0';
		tmpnames[cnt++] = tmpname;
	}
	tmpnames[numifs] = NULL;
	free(buf);
	*names = tmpnames;
	return (0);
}

/*
 * frees previously-allocated array from get_net_if_names
 */
void
free_net_if_names(char **ifnames)
{
	int	i;

	i = 0;
	while (ifnames[i] != NULL) {
		free(ifnames[i]);
		i++;
	}
	free(ifnames);
}


/*
 * attempt to remove ppa from end of file name
 * return -1 if none found
 * return ppa if found and remove the ppa from the filename
 */
static int
ifrm_num(char *fname, unsigned int *ppa)
{
	int	i;
	uint_t	p = 0;
	unsigned int	m = 1;

	i = strlen(fname) - 1;
	while (i >= 0 && '0' <= fname[i] && fname[i] <= '9') {
		p += (fname[i] - '0')*m;
		m *= 10;
		i--;
	}
	if (m == 1) {
		return (-1);
	}
	fname[i + 1] = '\0';
	*ppa = p;
	return (0);
}

/*
 * Open the device defined in dev_att with the given mode starting with
 * the module indicated by mod_cnt (1 indexed).  If mod_cnt > 0, fd must
 * contain the file descriptor that modules are to be pushed on.
 * Returns -1 if device could not be opened, the index of
 * the module that could not be pushed or 0 on success.
 */
static int
open_dev(dev_att_t *dev_att, int mode, int *fd, int mod_cnt)
{
	int	cnt;
	int	local_fd;

	if (debug)
		(void) printf("open_dev: ifname: %s : dev %s fd %d "
		    " mod_cnt %d\n",
		    dev_att->ifname, dev_att->devname, *fd, mod_cnt);
	/*
	 * if no module count is given, try and open the device
	 */
	if (mod_cnt == 0) {
		if (debug)
			(void) printf("open_dev: opening %s\n",
			    dev_att->devname);
		if ((local_fd = open(dev_att->devname, mode)) < 0) {
			if (debug) {
				perror("open_dev: device");
				(void) printf("\n");
			}
			*fd = local_fd;
			return (-1);
		}
		*fd = local_fd;
		cnt = 1;
	} else {
		local_fd = *fd;
		assert(local_fd > 0);
		cnt = mod_cnt;
	}

	/*
	 * Try and push modules (if any) onto the device stream
	 */
	for (; cnt <= dev_att->mod_cnt; cnt++) {
		if (debug)
			(void) printf(" pushing: mod %s",
			    dev_att->modlist[cnt - 1]);
		if (ioctl(local_fd, I_PUSH, dev_att->modlist[cnt - 1]) == -1) {
			if (debug) {
				perror("open_dev: push");
				(void) printf("\n");
			}
			return (cnt);
		}
	}
	if (debug)
		(void) printf("\n");
	return (0);
}

/*
 * Debug routine to print out dev_att_t structure
 */
static void
pf_dev_att(dev_att_t *dev_att)
{
	int cnt;

	(void) printf("\tifname: %s\n", dev_att->ifname);
	(void) printf("\t  style: %d\n", dev_att->style);
	(void) printf("\t  ppa: %d\n", dev_att->ppa);
	(void) printf("\t  mod_cnt: %d\n", dev_att->mod_cnt);
	(void) printf("\t  devname: %s\n", dev_att->devname);
	for (cnt = 0; cnt < dev_att->mod_cnt; cnt++) {
		(void) printf("\t      module: %s\n", dev_att->modlist[cnt]);
	}
}

/*
 * This function parses a '.' delimited interface name of the form
 * dev[.module[.module...]][:lun]
 * and places the device and module name into dev_att
 */
/* ARGSUSED */
static void
parse_ifname(dev_att_t *dev_att)
{
	char		*lunstr;
	char		*modlist = NULL; /* list of modules to push */
	int		cnt = 0; /* number of modules to push */
	char		modbuf[LIFNAMSIZ];
	char		*nxtmod;

	/*
	 * check for specified lun at end of interface and
	 * strip it off.
	 */
	lunstr = strchr(dev_att->ifname, ':');

	if (lunstr) {
		char *endptr;

		*lunstr = '\0';
		lunstr++;
		endptr = lunstr;
		dev_att->lun = strtoul(lunstr, &endptr, 10);

		if (endptr == lunstr || *endptr != '\0') {
			(void) printf("Invalid logical unit number:%s", lunstr);
			exit(-1);
		}
	} else {
		dev_att->lun = 0;
	}

	(void) strncpy(modbuf, dev_att->ifname, LIFNAMSIZ);

	/* parse '.' delmited module list */
	modlist = strchr(modbuf, '.');
	if (modlist) {
		/* null-terminate interface name (device) */
		*modlist = '\0';
		modlist++;
		if (strlen(modlist) == 0)
			modlist = NULL;
		while (modlist && cnt < MAX_MODS) {
			nxtmod = strchr(modlist, '.');
			if (nxtmod) {
				*nxtmod = '\0';
				nxtmod++;
			}
			(void) strncpy(dev_att->modlist[cnt], modlist,
			    LIFNAMSIZ);
			cnt++;
			modlist = nxtmod;
		}
	}
	(void) snprintf(dev_att->devname, LIFNAMSIZ, "%s/%s", DEVDIR, modbuf);
	dev_att->mod_cnt = cnt;
}

/*
 * given a interface name (with possible modules to push)
 * interface name must have the format of
 * dev[ppa][.module[.module...][ppa]][:lun]
 * where only one ppa may be specified e.g. ip0.foo.tun or ip.foo.tun0
 */
static int
ifname_open(char *dev_name, dev_att_t *dev_att)
{
	int		fd;
	uint_t		ppa;
	int		res;
	int		style;
	dl_info_ack_t	dl_info;
	int		mod_id;

	if (debug)
		(void) printf("ifname_open: %s\n", dev_name);

	if (strlen(dev_name) > LIFNAMSIZ - 1) {
		errno = EINVAL;
		return (-1);
	}

	/* save copy of original device name */
	(void) strncpy(dev_att->ifname, dev_name, LIFNAMSIZ);

	/* parse modules */
	parse_ifname(dev_att);

	/* try DLPI style 1 device first */

	if (debug) {
		pf_dev_att(dev_att);
	}
	mod_id = open_dev(dev_att, O_RDWR, &fd, 0);
	if (mod_id != 0) {
		if (debug) {
			(void) printf("Error on open_dev style 1 mod_id: %d"
			    " attemping style 2\n", mod_id);
			pf_dev_att(dev_att);
		}
		if (mod_id == -1) {
			res = ifrm_num(dev_att->devname, &ppa);
			mod_id = 0;
			if (res < 0) {
				if (debug)
					(void) fprintf(stderr,
					    "%s: No such file or directory\n",
					    dev_att->devname);
				(void) close(fd);
				return (-1);
			}
			/*
			 * ensure that it's the last module
			 * in the list to extract
			 * ppa
			 */
		} else if ((mod_id != dev_att->mod_cnt) ||
		    (res = ifrm_num(dev_att->modlist[dev_att->mod_cnt - 1],
			&ppa)) < 0) {
			if (debug) {
				(void) fprintf(stderr,
				    "Error on open_dev style 2 mod_id: %d \n",
				    mod_id);
			}
			if (mod_id == dev_att->mod_cnt)
				(void) fprintf(stderr, "ifconfig: could not "
				    "locate ppa in %s\n",
				    dev_att->ifname);
			(void) close(fd);
			return (-1);
		}
		goto style2;
	}
	dev_att->style = 1;
	dev_att->ppa = 0;
	style = DL_STYLE1;
	goto dl_info_chk;
style2:
	dev_att->ppa = ppa;
	mod_id = open_dev(dev_att, O_RDWR, &fd, mod_id);
	if (mod_id != 0) {
		if (debug) {
			(void) fprintf(stderr,
			    "Error on open_dev style 2 mod_id: %d \n",
			    mod_id);
			if (mod_id > 0) {
				(void) fprintf(stderr, "%s: No such module\n",
				    dev_att->modlist[mod_id - 2]);
			}
			pf_dev_att(dev_att);
		}
		(void) close(fd);
		return (-1);
	}
	dev_att->style = 2;
	style = DL_STYLE2;
dl_info_chk:
	if (dlpi_info_req(fd, &dl_info) < 0) {
		(void) close(fd);
		pf_dev_att(dev_att);
		return (-1);
	}
	if (dl_info.dl_provider_style != style) {
		if (debug) {
			(void) fprintf(stderr, "DLPI provider style mismatch: "
			    "expected style %s got style %s (0x%lx)\n",
			    style == DL_STYLE1 ? "1" : "2",
			    dl_info.dl_provider_style == DL_STYLE1 ? "1" : "2",
			    dl_info.dl_provider_style);
		}
		(void) close(fd);
		return (-1);
	}
	if (debug) {
		(void) printf("pars_dev_att() success\n");
		pf_dev_att(dev_att);
	}
	return (fd);
}

static int
dlpi_open_attach(char *ifname)
{
	int			fd;
	dev_att_t		dev_att;

	if (debug)
		(void) printf("dlpi_open_attach %s\n", ifname);

	/* if lun is specified fail (backwards compat) */
	if (strchr(ifname, ':') != NULL) {
		return (-1);
	}
	if ((fd = ifname_open(ifname, &dev_att)) < 0) {
		/* Not found */
		errno = ENXIO;
		return (-1);
	}
	if (dlpi_attach(fd, dev_att.ppa, dev_att.style) < 0) {
		(void) close(fd);
		return (-1);
	}
	return (fd);
}

static int
dlpi_attach(int fd, int ppa, int style)
{
	union DL_primitives	*dlp;
	char			*buf;
	struct strbuf		ctl;
	int			flags;

	if (style != 2)
		return (0);

	/* Allocate required buffers */
	if ((buf = malloc(BUFSIZ)) == NULL) {
		(void) fprintf(stderr, "ifconfig: malloc() failed\n");
		return (-1);
	}

	/* Issue DL_ATTACH_REQ */
	/* LINTED: malloc returns a pointer aligned for any use */
	dlp = (union DL_primitives *)buf;
	dlp->attach_req.dl_primitive = DL_ATTACH_REQ;
	dlp->attach_req.dl_ppa = ppa;
	ctl.buf = (char *)dlp;
	ctl.len = DL_ATTACH_REQ_SIZE;
	if (putmsg(fd, &ctl, NULL, 0) < 0) {
		perror("ifconfig: putmsg");
		free(buf);
		return (-1);
	}

	/* read reply */
	ctl.buf = (char *)dlp;
	ctl.len = 0;
	ctl.maxlen = BUFSIZ;
	flags = 0;

	/* start timeout for DL_OK_ACK reply */
	if (timed_getmsg(fd, &ctl, &flags, dlpi_timeout,
	    "DL_OK_ACK", "DL_ATTACH_REQ") == 0) {
		free(buf);
		return (-1);
	}

	if (debug) {
		(void) printf("ok_ack: ctl.len[%d] flags[%d]\n", ctl.len,
		    flags);
	}

	/* Validate DL_OK_ACK reply.  */
	if (ctl.len < sizeof (t_uscalar_t)) {
		(void) fprintf(stderr,
		    "ifconfig: attach failed: short reply to attach request\n");
		free(buf);
		return (-1);
	}

	if (dlp->dl_primitive == DL_ERROR_ACK) {
		if (debug)
			(void) fprintf(stderr,
			    "attach failed:  dl_errno %lu errno %lu\n",
			    dlp->error_ack.dl_errno,
			    dlp->error_ack.dl_unix_errno);
		free(buf);
		errno = ENXIO;
		return (-1);
	}
	if (dlp->dl_primitive != DL_OK_ACK) {
		(void) fprintf(stderr,
		    "ifconfig: attach failed: "
		    "unrecognizable dl_primitive %lu received",
		    dlp->dl_primitive);
		free(buf);
		return (-1);
	}
	if (ctl.len < DL_OK_ACK_SIZE) {
		(void) fprintf(stderr,
		    "ifconfig: attach failed: "
		    "short attach acknowledgement received\n");
		free(buf);
		return (-1);
	}
	if (dlp->ok_ack.dl_correct_primitive != DL_ATTACH_REQ) {
		(void) fprintf(stderr,
		    "ifconfig: attach failed: "
		    "returned prim %lu != requested prim %lu\n",
		    dlp->ok_ack.dl_correct_primitive,
		    (t_uscalar_t)DL_ATTACH_REQ);
		free(buf);
		return (-1);
	}
	if (debug)
		(void) printf("attach done\n");

	free(buf);
	return (0);
}

static int
dlpi_get_phys(int fd, uchar_t *eaddr)
{
	union DL_primitives	*dlp;
	char			*buf;
	struct strbuf		ctl;
	int			flags;

	/* Allocate required buffers */
	if ((buf = malloc(BUFSIZ)) == NULL) {
		(void) fprintf(stderr, "ifconfig: malloc() failed\n");
		return (-1);
	}
	/* Issue DL_PHYS_ADDR_REQ */
	/* LINTED: malloc returns a pointer aligned for any use */
	dlp = (union DL_primitives *)buf;
	dlp->physaddr_req.dl_primitive = DL_PHYS_ADDR_REQ;
	dlp->physaddr_req.dl_addr_type = DL_CURR_PHYS_ADDR;
	ctl.buf = (char *)dlp;
	ctl.len = DL_PHYS_ADDR_REQ_SIZE;
	if (putmsg(fd, &ctl, NULL, 0) < 0) {
		perror("ifconfig: putmsg");
		free(buf);
		return (-1);
	}

	/* read reply */
	ctl.buf = (char *)dlp;
	ctl.len = 0;
	ctl.maxlen = BUFSIZ;
	flags = 0;

	if (timed_getmsg(fd, &ctl, &flags, dlpi_timeout,
	    "DL_PHYS_ADDR_ACK", "DL_PHYS_ADDR_REQ (DL_CURR_PHYS_ADDR)") == 0) {
		free(buf);
		return (-1);
	}

	if (debug) {
		(void) printf("phys_addr_ack: ctl.len[%d] flags[%d]\n", ctl.len,
		    flags);
	}

	/* Validate DL_PHYS_ADDR_ACK reply.  */
	if (ctl.len < sizeof (t_uscalar_t)) {
		(void) fprintf(stderr, "ifconfig: phys_addr failed: "
		    "short reply to phys_addr request\n");
		free(buf);
		return (-1);
	}

	if (dlp->dl_primitive == DL_ERROR_ACK) {
		/*
		 * Do not print errors for DL_UNSUPPORTED and DL_NOTSUPPORTED
		 */
		if (dlp->error_ack.dl_errno != DL_UNSUPPORTED &&
		    dlp->error_ack.dl_errno != DL_NOTSUPPORTED) {
			(void) fprintf(stderr, "ifconfig: phys_addr failed: "
			    "dl_errno %lu errno %lu\n",
			    dlp->error_ack.dl_errno,
			    dlp->error_ack.dl_unix_errno);
		}
		free(buf);
		return (-1);
	}
	if (dlp->dl_primitive != DL_PHYS_ADDR_ACK) {
		(void) fprintf(stderr, "ifconfig: phys_addr failed: "
		    "unrecognizable dl_primitive %lu received\n",
		    dlp->dl_primitive);
		free(buf);
		return (-1);
	}
	if (ctl.len < DL_PHYS_ADDR_ACK_SIZE) {
		(void) fprintf(stderr, "ifconfig: phys_addr failed: "
		    "short phys_addr acknowledgement received\n");
		free(buf);
		return (-1);
	}
	/* Check length of address. */
	if (dlp->physaddr_ack.dl_addr_length != ETHERADDRL)
		return (-1);

	/* copy Ethernet address */
	(void) memcpy(eaddr, &buf[dlp->physaddr_ack.dl_addr_offset],
	    ETHERADDRL);

	free(buf);
	return (0);
}



static int
dlpi_info_req(int fd, dl_info_ack_t *info_ack)
{
	dl_info_req_t   info_req;
	int	buf[BUFSIZ/sizeof (int)];
	union DL_primitives	*dlp = (union DL_primitives *)buf;
	struct  strbuf  ctl;
	int	flags;

	info_req.dl_primitive = DL_INFO_REQ;

	ctl.len = DL_INFO_REQ_SIZE;
	ctl.buf = (char *)&info_req;

	flags = RS_HIPRI;

	if (putmsg(fd, &ctl, (struct strbuf *)NULL, flags) < 0) {
		perror("ifconfig: putmsg");
		return (-1);
	}

	/* read reply */
	ctl.buf = (char *)dlp;
	ctl.len = 0;
	ctl.maxlen = BUFSIZ;
	flags = 0;
	/* start timeout for DL_BIND_ACK reply */
	if (timed_getmsg(fd, &ctl, &flags, dlpi_timeout, "DL_INFO_ACK",
	    "DL_INFO_ACK") == 0) {
		return (-1);
	}

	if (debug) {
		(void) printf("info_ack: ctl.len[%d] flags[%d]\n", ctl.len,
		    flags);
	}

	/* Validate DL_BIND_ACK reply.  */
	if (ctl.len < sizeof (t_uscalar_t)) {
		(void) fprintf(stderr,
		    "ifconfig: info req failed: short reply to info request\n");
		return (-1);
	}

	if (dlp->dl_primitive == DL_ERROR_ACK) {
		(void) fprintf(stderr,
		    "ifconfig: info req failed:  dl_errno %lu errno %lu\n",
		    dlp->error_ack.dl_errno, dlp->error_ack.dl_unix_errno);
		return (-1);
	}
	if (dlp->dl_primitive != DL_INFO_ACK) {
		(void) fprintf(stderr,
		    "ifconfig: info req failed: "
		    "unrecognizable dl_primitive %lu received\n",
		    dlp->dl_primitive);
		return (-1);
	}
	if (ctl.len < DL_INFO_ACK_SIZE) {
		(void) fprintf(stderr,
		    "ifconfig: info req failed: "
		    "short info acknowledgement received\n");
		return (-1);
	}
	*info_ack = *(dl_info_ack_t *)dlp;
	return (0);
}


/*
 * interface called from ifconfig.c to get the ethernet address - jhf
 */
int
dlpi_get_address(char *ifname, struct ether_addr *ea)
{
	int 	fd;

	if (debug)
		(void) printf("dlpi_get_address: dlpi_open_attach\t");
	fd = dlpi_open_attach(ifname);
	if (fd < 0) {
		/* Do not report an error */
		return (-1);
	}

	if (debug)
		(void) printf("dlpi_get_address: dlpi_get_phys %s\n", ifname);
	if (dlpi_get_phys(fd, (uchar_t *)ea) < 0) {
		(void) close(fd);
		return (-1);
	}
	(void) close(fd);
	return (0);
}

static int
timed_getmsg(int fd, struct strbuf *ctlp, int *flagsp, int timeout, char *kind,
    char *request)
{
	char		perrorbuf[BUFSIZ];
	struct pollfd	pfd;
	int		ret;

	pfd.fd = fd;

	pfd.events = POLLIN | POLLRDNORM | POLLRDBAND | POLLPRI;
	if ((ret = poll(&pfd, 1, timeout * 1000)) == 0) {
		(void) fprintf(stderr, "ifconfig: %s timed out\n", kind);
		return (0);
	} else if (ret == -1) {
		(void) snprintf(perrorbuf, sizeof (perrorbuf),
		    "ifconfig: poll for %s from %s", kind, request);
		perror(perrorbuf);
		return (0);
	}

	/* poll returned > 0 for this fd so getmsg should not block */
	if ((ret = getmsg(fd, ctlp, NULL, flagsp)) < 0) {
		(void) snprintf(perrorbuf, sizeof (perrorbuf),
		    "ifconfig: getmsg expecting %s for %s", kind, request);
		perror(perrorbuf);
		return (0);
	}

	return (1);
}
