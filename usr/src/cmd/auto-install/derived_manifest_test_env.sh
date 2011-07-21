#!/bin/ksh
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.

# This file contains mock settings of environment variables which are set
# in the environment in which a Derived Manifests script is run.
#
# A copy of this file may be used to set up an environment for testing
# a Derived Manifests script.
#
# Adjust the variables in the copy to accurately represent the AI client
# environment in which the script will be run.  Then source the copy, set
# AIM_MANIFEST to specify the resultant derived manifest file, and run the
# Derived Manifests script-under-test as the aiuser role via su.
#
# Optionally set AIM_LOGFILE to specify a logfile into which status will be
# written which will be appended each time aimanifest(1M) is invoked by the
# script.
#
# # . this_file
# # export AIM_MANIFEST=/tmp/derived.xml
# # export AIM_LOGFILE=/tmp/aimanifest_log
# # su aiuser -c dm_script.sh
#

# -- Variables dealing with the service environment running on the AI client.

# URL of this manifest script.
export SI_MANIFEST_SCRIPT=derived_manifest_test_env.sh

# The name of the install service used to obtain this manifest script.
# Filled in when AI client is booted over the network.
export SI_INSTALL_SERVICE=default-sparc

# -- Variables dealing with the architecture or platform of the AI client.

# The native instruction set architecture.
# Equivalent to the output of `isainfo -n`.
export SI_NATISA=sparcv9

# The architecture.  Equivalent to the output of `uname -p`.
export SI_ARCH=sparc
export SI_CPU=sparc

# The kernel architecture.  Equivalent to the output of `uname -m`.
export SI_KARCH=sun4v

# The model name and platform.  Equivalent to the output of  `uname -i`.
export SI_MODEL=SUNW,T5140
export SI_PLATFORM=SUNW,T5140

# The amount of physical memory in MB.
export SI_MEMSIZE=4294967296

# -- Variables dealing with network environment of the AI client.

# The hostname.
export SI_HOSTNAME=sparky

# The host address, as set in the install environment.
export SI_HOSTADDRESS=10.11.12.13

# The network number: IP address & Netmask
export SI_NETWORK=10.11.12.0/24

# -- Variables dealing with target disks of the AI client.
# -- Here, two disks are shown, but the actual number will vary by system.

# Each disk will have a name and a size in MB.
export SI_DISKNAME_1=/dev/rdsk/c0t0d0s0
export SI_DISKSIZE_1=476940

export SI_DISKNAME_2=/dev/rdsk/c0t1d0s0
export SI_DISKSIZE_2=476940

export SI_NUMDISKS=2

