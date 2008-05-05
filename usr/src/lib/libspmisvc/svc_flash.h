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



#ifndef _SVC_FLASH_H
#define	_SVC_FLASH_H


/*
 * Functions specific to the Flash retrieval methods
 */

#ifdef __cplusplus
extern "C" {
#endif

#include "spmisvc_api.h"

/* typedef'd to FlashOps in spmisvc_api.h */
struct _flash_ops {
	FlashError (*open)(FlashArchive *);
	FlashError (*readline)(FlashArchive *, char **);
	FlashError (*extract)(FlashArchive *, FILE *, TCallback *, void *);
	FlashError (*close)(FlashArchive *);
};

typedef struct {
	FILE		*file;
	long long	fsize;
} FileData;

#define	FLASH_DEBUG \
	LOG, get_trace_level() > 0, "LIBSPMISVC", DEBUG_LOC, LEVEL0


/* svc_flash_http.c */
FlashError	FLARHTTPOpen(FlashArchive *);
FlashError	FLARHTTPReadLine(FlashArchive *, char **);
FlashError	FLARHTTPExtract(FlashArchive *, FILE *, TCallback *, void *);
FlashError	FLARHTTPClose(FlashArchive *);

/* svc_flash_http_old.c */
FlashError	_old_FLARHTTPOpen(FlashArchive *);
FlashError	_old_FLARHTTPReadLine(FlashArchive *, char **);
FlashError	_old_FLARHTTPExtract(FlashArchive *, FILE *, TCallback *,
    void *);
FlashError	_old_FLARHTTPClose(FlashArchive *);

/* svc_flash_ftp.c */
FlashError	FLARFTPOpen(FlashArchive *);
FlashError	FLARFTPReadLine(FlashArchive *, char **);
FlashError	FLARFTPExtract(FlashArchive *, FILE *, TCallback *, void *);
FlashError	FLARFTPClose(FlashArchive *);

/* svc_flash_lf.c */
FlashError	FLARLocalFileOpen(FlashArchive *);
FlashError	FLARLocalFileReadLine(FlashArchive *, char **);
FlashError	FLARLocalFileExtract(FlashArchive *, FILE *, TCallback *,
			void *);
FlashError	FLARLocalFileClose(FlashArchive *);

FlashError	FLARLocalFileOpenPriv(FlashArchive *, FileData *, char *);
FlashError	FLARLocalFileReadLinePriv(FlashArchive *, FileData *, char **);
FlashError	FLARLocalFileExtractPriv(FlashArchive *, FileData *, FILE *,
			TCallback *, void *);
FlashError	FLARLocalFileClosePriv(FlashArchive *, FileData *);

/* svc_flash_nfs.c */
FlashError	FLARNFSOpen(FlashArchive *);
FlashError	FLARNFSReadLine(FlashArchive *, char **);
FlashError	FLARNFSExtract(FlashArchive *, FILE *, TCallback *, void *);
FlashError	FLARNFSClose(FlashArchive *);

/* svc_flash_ld.c */
FlashError	FLARLocalDeviceOpen(FlashArchive *);
FlashError	FLARLocalDeviceReadLine(FlashArchive *, char **);
FlashError	FLARLocalDeviceExtract(FlashArchive *, FILE *, TCallback *,
			void *);
FlashError	FLARLocalDeviceClose(FlashArchive *);

/* svc_flash_tape.c */
FlashError	FLARLocalTapeOpen(FlashArchive *);
FlashError	FLARLocalTapeReadLine(FlashArchive *, char **);
FlashError	FLARLocalTapeExtract(FlashArchive *, FILE *, TCallback *,
			void *);
FlashError	FLARLocalTapeClose(FlashArchive *);

#ifdef __cplusplus
}
#endif

#endif /* _SVC_FLASH_H */
