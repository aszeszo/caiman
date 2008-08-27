#!/usr/bin/python
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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
CHECKPOINT_ENABLE = "distro_constr_params/distro_constr_flags/checkpoint_enable"
PKG_IMAGE_AREA = "img_params/pkg_image_area"
DISTRO_NAME = "name"
DEFAULT_MAIN_AUTHNAME = "distro_constr_params/pkg_repo_default_authority/main/authname"
DEFAULT_MAIN_URL = "distro_constr_params/pkg_repo_default_authority/main/url"
STOP_ON_ERR = "distro_constr_params/distro_constr_flags/stop_on_error"
DEFAULT_MAIN_NODE =  "distro_constr_params/pkg_repo_default_authority/main/"
ADD_AUTH_MAIN_NODE = "distro_constr_params/pkg_repo_addl_authority/main/"
PKG_NAME =  "img_params/packages/pkg/name"
CHECKPOINT_RESUME = "distro_constr_params/distro_constr_flags/checkpoint_enable/resume_from"
OUTPUT_IMAGE = "img_params/output_image"
OUTPUT_PATH = OUTPUT_IMAGE + "/pathname"
USER = "img_params/user"
USER_UID = USER + "/UID"
LOCALE_LIST = "img_params/locale_list"
