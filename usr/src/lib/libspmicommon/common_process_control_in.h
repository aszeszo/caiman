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


#ifndef	_PROCESS_CONTROL_IN_H
#define	_PROCESS_CONTROL_IN_H

#pragma ident	"@(#)common_process_control_in.h	1.5	07/11/12 SMI"

#include<sys/types.h>
#include<termios.h>
#include<sys/ioctl.h>
#include<limits.h>

#include"spmicommon_api.h"

/*
 * Define the structure to hold the data for the process being
 * controlled.
 */

#define	PROCESS_INITIALIZED 0xDEADBEEF
typedef struct {
	unsigned int	Initialized;
	char		Image[PATH_MAX];
	char		**argv;
	TPCState	State;
	pid_t		PID;
	TPCFD		FD;
	TPCFILE		FILE;
} TPCB;

/*
 * *********************************************************************
 * Function Name: PCValidateHandle				       *
 *								       *
 * Description:							       *
 *   This function takes in a process handle and determines if it is   *
 *   valid.  Upon Success, the function returns Zero and on failure    *
 *   returns non-zero.						       *
 *								       *
 * Return:							       *
 *  Type			     Description		       *
 *  TPCError			     Upon successful completion the    *
 *				     PCSuccess flag is returned.  Upon *
 *				     failure the appropriate error     *
 *				     code is returned.		       *
 * Parameters:							       *
 *  Type			     Description		       *
 *  TPCHandle			     The handle that is to be	       *
 *				     validated.			       *
 *								       *
 * Designer/Programmer: Craig Vosburgh/RMTC (719)528-3647	       *
 * *********************************************************************
 */

static	TPCError
PCValidateHandle(TPCHandle Handle);

#endif	/* _PROCESS_CONTROL_IN_H */
