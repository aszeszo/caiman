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


#ifndef lint
#pragma ident	"@(#)soft_swi_webstart_util.c	1.4	07/11/09 SMI"
#endif

#include "spmisoft_api.h"
#include "sw_swi.h"

char *
readInText(char *fullpath)
{
	char	*c;

	enter_swlib("readInText");
	c = (char *)swi_readInText(fullpath);
	exit_swlib();
	return (c);
}

int
writeOutText(char *fullpath, char *mode, char *line)
{
	int	i;

	enter_swlib("writeOutText");
	i = swi_writeOutText(fullpath, mode, line);
	exit_swlib();
	return (i);
}

int
concatFiles(StringList *fileList, char *outputfile)
{
	int	i;

	enter_swlib("concatFiles");
	i = swi_concatFiles(fileList, outputfile);
	exit_swlib();
	return (i);
}

int
copyFile(char *srcFilePath, char *destFilePath, boolean_t preserve_perm)
{
	int	i;

	enter_swlib("copyFile");
	i = swi_copyFile(srcFilePath, destFilePath, preserve_perm);
	exit_swlib();
	return (i);
}

int
copyDir(char *srcDirPath, char *destDirPath)
{
	int	i;

	enter_swlib("copyDir");
	i = swi_copyDir(srcDirPath, destDirPath);
	exit_swlib();
	return (i);
}

int
mkdirs(char *dirpath)
{
	int	i;

	enter_swlib("mkdirs");
	i = swi_mkdirs(dirpath);
	exit_swlib();
	return (i);
}

CDToc *
readCDTOC(char *mountpt)
{
	CDToc	*cdtoc;

	enter_swlib("readCDTOC");
	cdtoc = (CDToc *)swi_readCDTOC(mountpt);
	exit_swlib();
	return (cdtoc);
}

void
free_cdtoc(CDToc *cdtoc)
{
	enter_swlib("free_cdtoc");
	swi_free_cdtoc(cdtoc);
	exit_swlib();
}

int
pingHost(char *host)
{
	int	i;

	enter_swlib("pingHost");
	i = swi_pingHost(host);
	exit_swlib();
	return (i);
}

char *
getLocString()
{
	char	*c;

	enter_swlib("getLocString");
	c = (char *)swi_getLocString();
	exit_swlib();
	return (c);
}

void
setWebstartLocale(char *locale)
{
	enter_swlib("setWebstartLocale");
	swi_setWebstartLocale(locale);
	exit_swlib();
}

char *
getWebstartLocale()
{
	char *c;

	enter_swlib("getWebstartLocale");
	c = (char *)swi_getWebstartLocale();
	exit_swlib();
	return (c);
}

void
check_boot_environment()
{
	enter_swlib("check_boot_environment");
	swi_check_boot_environment();
	exit_swlib();
}

int
isBootFromDisc()
{
	int	i;

	enter_swlib("isBootFromDisc");
	i = (int)swi_isBootFromDisc();
	exit_swlib();
	return (i);
}

int
installAfterReboot()
{
	int	i;

	enter_swlib("installAfterReboot");
	i = (int)swi_installAfterReboot();
	exit_swlib();
	return (i);
}
