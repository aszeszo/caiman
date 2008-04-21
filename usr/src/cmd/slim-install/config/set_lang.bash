#!/usr/bin/bash
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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

# list of suported languages
LANG_NAMES=("1. Chinese - Simplified" "2. Chinese - Traditional" "3. English" \
    "4. French" "5. German" "6. Italian" "7. Japanese" "8. Korean" \
    "9. Portuguese - Brazil" "10. Russian" "11. Spanish" "12. Swedish")

# corresponding list of default locales
LANG_VALUES=(zh_CN.UTF-8 zh_TW.UTF-8 en_US.UTF-8 fr_FR.UTF-8 de_DE.UTF-8 \
    it_IT.UTF-8 ja_JP.UTF-8 ko_KR.UTF-8 pt_BR.UTF-8 ru_RU.UTF-8 es_ES.UTF-8 \
    sv_SE.UTF-8)

# English is the default
DEF_LANG=3

# prompt
LANG_UI_PROMPT="To select the desktop language, enter a number [default $DEF_LANG]:"

echo

# list supported languages
for i in 0 1 2 3 4 5 6 7 8 9 10 11 ; do
	echo ${LANG_NAMES[i]}
done

# prompt user to select language
# check for valid entry
# empty string means default choice
LANG_CHOICE=""
while [ -z $LANG_CHOICE ] ; do
	echo -n $LANG_UI_PROMPT
	read LANG_CHOICE

	# if pressed Enter, pick up default value
	[ -z $LANG_CHOICE ] && LANG_CHOICE=$DEF_LANG

	# check for valid option
	[ "$LANG_CHOICE" != "${LANG_CHOICE%[!0-9]*}" ] || [ $LANG_CHOICE -lt 1 -o $LANG_CHOICE -gt 12 ] && LANG_CHOICE=""
done

mkdir -p /etc/sysconfig

# store the selected language to the gdm configuration file
echo "RC_LANG=${LANG_VALUES[$LANG_CHOICE - 1]}" > /etc/sysconfig/language
