#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#

#
# Copyright (c) 2007, 2011, Oracle and/or its affiliates. All rights reserved.
#

# Configuration variables for the runtime environment of the nightly
# build script and other tools for construction and packaging of releases.
# This script is sourced by 'nightly' and 'bldenv' to set up the environment
# for the build. This example is suitable for building a developers workspace,
# which will contain the resulting packages and archives. It is based off
# the Install Nevada release. It sets NIGHTLY_OPTIONS to make nightly do:
#	DEBUG and non-DEBUG builds (-D)
#	runs lint in usr/src (-l plus the LINTDIRS variable)
#	sends mail on completion (-m and the MAILTO variable)
#	creates packages for PIT/RE (-p)
#	does not run protocmp (-N); packages are a mess
#
# Options known not to work (yet) in Install are:
#	-C	'make check' cstyle target is not present
#	-S#	no source product
#	-X	no such thing as Install IHV
#	-a	bfu archives not used in Install
#	-r	ELF runtime checking needs some help for ON references
#	-t	tools are not separately packaged yet
#
# Other features disabled:
#	CHECK_PATHS	no packaging exception list
#
export NIGHTLY_OPTIONS="-AMNdlmp +t";

# This is a variable for the rest of the script - GATE doesn't matter to
# nightly itself
export GATE=slim_source;

# CODEMGR_WS - where is your workspace at (or what should nightly name it)
export CODEMGR_WS="/export/home/${LOGNAME}/${GATE}";

# PARENT_WS is used to determine the parent of this workspace. This is
# for the options that deal with the parent workspace (such as where the
# proto area will go).
export PARENT_WS="ssh://anon@hg.opensolaris.org/hg/caiman/slim_source";


# CLONE_WS is the workspace nightly should do a bringover from. Since it's
# going to bringover usr/src, this could take a while, so we use the
# clone instead of the gate (see the gate's README).
export CLONE_WS="ssh://anon@hg.opensolaris.org/hg/caiman/slim_source";

# The bringover, if any, is done as STAFFER.
# Set STAFFER to your own login as gatekeeper or developer
# The point is to use group "staff" and avoid referencing the parent
# workspace as root.
# Some scripts optionally send mail messages to MAILTO.
#
export STAFFER="$LOGNAME";
export MAILTO="$STAFFER";

# The project (see project(4)) under which to run this build.  If not
# specified, the build is simply run in a new task in the current project.
export BUILD_PROJECT=;

# You should not need to change the next four lines
export LOCKNAME="$(basename "${CODEMGR_WS}")_nightly.lock";
export ATLOG="${CODEMGR_WS}/log";
export LOGFILE="${ATLOG}/nightly.log";
export MACH="$(uname -p)";

# For employees of Oracle Corp. only:
#
#     When releasing a binary distribution under a non-CDDL license,
#     such as the OTN, the CDDL may be stripped to avoid end user
#     confusion.  To accomplish this, we uncomment this assignment.
#
# All others:
#
#     You must comment out this assignment to preserve CDDL text unmodified.
#
INS_STRIP_CDDL= ; export INS_STRIP_CDDL

# REF_PROTO_LIST - for comparing the list of stuff in your proto area
# with. Generally this should be left alone, since you want to see differences
# from your parent (the gate).
#
export REF_PROTO_LIST="${PARENT_WS}/usr/src/proto_list_${MACH}";

# where cpio archives of the OS are placed. Usually this should be left
# alone too.
export CPIODIR="${CODEMGR_WS}/archives/${MACH}/nightly";

#
# build environment variables, including version info for mcs, motd,
# motd, uname and boot messages. Mostly you shouldn't change this except
# when the release slips (nah) or you move an environment file to a new
# release
#
export ROOT="${CODEMGR_WS}/proto/root_${MACH}";
export SRC="${CODEMGR_WS}/usr/src";
export DVDSRC="${SRC}/cmd/gui";

export CDVERSION="11";
export VERSION="5.${CDVERSION}";
export ARCH="$(uname -p)";

unset DISPLAY PKGINFODIR PKGNAME PROTOTYPE

# Pointers to alternate versions of ON and SFW.  Defaults to build machine.
#ONREF_GATE="";                         export ONREF_GATE
#SFWREF_GATE="";                        export SFWREF_GATE

#
# the RELEASE and RELEASE_DATE variables are set in Makefile.master;
# there might be special reasons to override them here, but that
# should not be the case in general
#
# RELEASE="5.10.1";                     export RELEASE
# RELEASE_DATE="October 2007";          export RELEASE_DATE

# proto area in parent for optionally depositing a copy of headers and
# libraries corresponding to the protolibs target
# not applicable given the NIGHTLY_OPTIONS
#
export PARENT_ROOT="${PARENT_WS}/proto/root_${MACH}";

#
#       package creation variable. you probably shouldn't change this either.
#
export PKGARCHIVE="${CODEMGR_WS}/packages/${MACH}/nightly";

# we want make to do as much as it can, just in case there's more than
# one problem.
export MAKEFLAGS=k;

# Magic variable to prevent the devpro compilers/teamware from sending
# mail back to devpro on every use.
export UT_NO_USAGE_TRACKING="1";

# Build tools - don't set these unless you know what you're doing.  These
# variables allows you to get the compilers and onbld files locally or
# through cachefs.  Set BUILD_TOOLS to pull everything from one location.
# Alternately, you can set ONBLD_TOOLS to where you keep the contents of
# SUNWonbld and SPRO_ROOT to where you keep the compilers.
#
#BUILD_TOOLS=/opt;					export BUILD_TOOLS
#ONBLD_TOOLS=/opt/onbld;				export ONBLD_TOOLS
#SPRO_ROOT=/opt/SUNWspro;				export SPRO_ROOT

# This goes along with lint - it is a series of the form "A [y|n]" which
# means "go to directory A and run 'make lint'" Then mail me (y) the
# difference in the lint output. 'y' should only be used if the area you're
# linting is actually lint clean or you'll get lots of mail.
# You shouldn't need to change this though.
#LINTDIRS="$SRC y";	export LINTDIRS

# Set this flag to 'n' to disable the automatic validation of the dmake
# version in use.  The default is to check it.
#CHECK_DMAKE=y

# Set this flag to 'n' to disable the use of 'checkpaths'.  The default,
# if the 'N' option is not specified, is to run this test.
CHECK_PATHS=n

# Set this flag to 'y' to enable the use of elfsigncmp to validate the
# output of elfsign.  Doing so requires that 't' be set in NIGHTLY_OPTIONS.
# The default is to not verify them.
#VERIFY_ELFSIGN=n


# POST_NIGHTLY can be any command to be run at the end of nightly.  See
# nightly(1) for interactions between environment variables and this command.
#POST_NIGHTLY=
