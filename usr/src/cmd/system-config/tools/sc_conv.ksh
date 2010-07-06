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
#
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

#
# This script converts SC manifest from old format (build < 144) to
# the new one introduced in build 144.
#
# It is part of the AI image and is utilized by Automated Installer
# when user provides SC manifest in old format. In such case, SC manifest
# is converted to the new format during the installation.
#
# In order to ease the transition, the script can be also used as a conversion
# tool on AI server side (e.g. by administrator) to convert existing SC
# manifests to the new format.
#
# Following formats of SC manifests are supported:
#  * standalone SC manifest
#  * manifest embedded in AI combined manifest as XML comment
#

#
# Establish PATH for non-built in commands
#
export PATH=/usr/bin:/usr/sbin

SC_EMBEDDED_TAG="<sc_embedded_manifest"
MANIFEST_TMP=/tmp/manifest_tmp.$$
SC_VALUE_RE_BEG=".*[\040\009]value[\040\009]*=[\040\009]*[\042\047]"
SC_VALUE_RE_END="[\042\047][\040\009]*\/>.*\$"

# builtins
builtin cat
builtin grep
builtin rm

#
# Print error message to stderr and exit
#
error_exit() {
	print -u2 "$@"

	exit 1
}

#
# create_new_manifest
#
# Description:
#     Create manifest containing template SC manifest in new format.
#     If combined manifest was provided, copy install portion of AI manifest,
#     since it has not changed.
#
# Parameters:
#     $1 - old manifest
#     $2 - new manifest
#     $3 - true  - old manifest is combined AI manifest
#          false - old manifest is standalone SC manifest
#
create_new_manifest()
{
	typeset src_man="$1"
	typeset dst_man="$2"
	typeset is_combined="$3"

	#
	# If it is combined AI manifest, copy AI portion of it and embed
	# SC manifest as a comment, since this is how it is currently handled.
	# On the other hand, standalone SC manifest is standard XML file.
	#
	if $is_combined; then
		nawk '{ print } ; $0 ~ end_tag { exit }' \
		    end_tag="$SC_EMBEDDED_TAG" "$src_man" > "$dst_man"

		print "<!-- <?xml version='1.0'?>" >> "$dst_man"
	else
		print "<?xml version='1.0'?>" > "$dst_man"
	fi

	cat <<-EOF >> "$dst_man"
<!DOCTYPE service_bundle SYSTEM "/usr/share/lib/xml/dtd/service_bundle.dtd.1">
<service_bundle type="profile" name="system configuration">
    <service name="system/install/config" version="1" type="service">
        <instance name="default" enabled="true">
            <property_group name="user_account" type="application">
                <propval name="login" type="astring" value=""/>
                <propval name="password" type="astring" value=""/>
                <propval name="description" type="astring" value=""/>
                <propval name="shell" type="astring" value="/usr/bin/bash"/>
                <propval name="uid" type='count' value='101'/>
                <propval name="gid" type='count' value='10'/>
                <propval name="type" type="astring" value="normal"/>
                <propval name="roles" type="astring" value="root"/>
            </property_group>

            <property_group name="root_account" type="application">
                <propval name="password" type="astring" value=""/>
                <propval name="type" type="astring" value="role"/>
            </property_group>

            <property_group name="other_sc_params" type="application">
                <propval name="timezone" type="astring" value=""/>
                <propval name="hostname" type="astring" value=""/>
            </property_group>
        </instance>
    </service>

    <service name="system/console-login" version="1" type="service">
        <property_group name="ttymon" type="application">
            <propval name="terminal_type" type="astring" value="sun"/>
        </property_group>
    </service>

    <service name="network/physical" version="1" type="service">
        <instance name="nwam" enabled="true"/>
        <instance name="default" enabled="false"/>
    </service>
</service_bundle>
	EOF

	# if combined AI manifest, finish it by appropriate XML end tags
	if $is_combined; then
	cat <<-EOF >> "$dst_man"
 -->
    </sc_embedded_manifest>
</ai_criteria_manifest>
	EOF
	fi
}

#
# get_value
#
# Description:
#     Obtains value of given XML tag from old SC manifest
#     XML parser obeys the same set of rules as AI parser and makes the same
#     assumptions. This approach assures that if SC manifest validates in AI,
#     it is also valid for purposes of this conversion.
#
# Rules and assumptions:
#  - Whole SC element along with its 'name', 'type' and 'value' attributes
#    fits one line
#  - tokens are separated by one or more spaces or tabulators
#  - 'value' attributes are quoted by single or double quotes,
#    e.g. both value="opensolaris" or value='opensolaris' are allowed
#
#
# Parameters:
#     $1 - XML tag name
#     $2 - path to old manifest
#
get_value()
{
	typeset xml_tag="$1"
	typeset old_sc_manifest="$2"

	nawk '{ if (match($0, "<propval.*" tag ".*\/>") != 0) { \
	    sub(re_beg,""); sub(re_end,""); print ; exit }}' \
	    re_beg="$SC_VALUE_RE_BEG" re_end="$SC_VALUE_RE_END" \
	    tag=$xml_tag "$old_sc_manifest"
}

### MAIN ###
if (( $# != 2 )) ; then
	error_exit "Usage: $0 old_manifest.xml new_manifest.xml"
fi

typeset manifest_old="$1"
typeset manifest_new="$2"

# check if source can be accessed
if [[ ! -f "$manifest_old" ]] ; then
	error_exit "Could not access original AI manifest $manifest_old," \
	    "aborting."
fi

# if destination file exists, inform user that it will be overwritten
if [[ -f "$manifest_new" ]] ; then
	print "$manifest_new exists, it will be saved to" \
	    "$manifest_new.saved."

	mv "$manifest_new" "${manifest_new}.saved"

	if (( $? != 0 )) ; then
		error_exit "Failed to move "$manifest_new" to" \
		    "${manifest_new}.saved, aborting."
	fi
fi

# create temporary ai manifest
touch "$MANIFEST_TMP"

if (( $? != 0 )) ; then
	error_exit "Failed to create temporary file $MANIFEST_TMP, aborting."
fi

#
# Convert old SC manifest to new format. SC manifest can be provided in two
# forms. Either embedded in combined AI manifest or as a standalone file.
# Detect the form we are going to deal with and take appropriate approach.
#
# For combined AI manifest:
#  * Copy install portion of AI manifest, since it has not changed
# Rest of steps is the same for both forms:
#  * Append SC template compliant with new format
#  * Replace SC parameters in SC template with the ones taken from original
#    SC manifest
#

#
# Detect form of provided manifest
# In case of combined AI manifest, SC portion is enclosed in XML tag
# SC_EMBEDDED_TAG
#
grep $SC_EMBEDDED_TAG $manifest_old > /dev/null 2>&1

if (( $? == 0 )) ; then
	print "Provided SC manifest is part of AI combined manifest."
	is_combined_manifest=true
else
	print "Standalone SC manifest provided."
	is_combined_manifest=false
fi

#
# Start with creating manifest which contains SC template manifest in new
# format while keeping rest of content untouched.
#
create_new_manifest "$manifest_old" "$MANIFEST_TMP" $is_combined_manifest

#
# Populate SC parameters in new manifest from those defined in old manifest
# First obtain SC parameters from old manifest
#

username=$(get_value "username" "$manifest_old")
userpass=$(get_value "userpass" "$manifest_old")
description=$(get_value "description" "$manifest_old")
rootpass=$(get_value "rootpass" "$manifest_old")
timezone=$(get_value "timezone" "$manifest_old")
nodename=$(get_value "hostname" "$manifest_old")

print username=$username
print userpass=$userpass
print description=$description
print rootpass=$rootpass
print timezone=$timezone
print nodename=$nodename

#
# Populate SC parameters in new SC manifest from obtained values.
# If particular parameter is not defined in original manifest (has been read
# as empty string), do not populate it in new manifest either.
#
nawk ' \
    { skip = "false" } \
    /<property_group name="user_account"/ { pconf = "user" } \
    /<property_group name="root_account"/ { pconf = "root" } \
    /<propval.*login/ { \
        sub(/value="/, "&" login); if (login == "") skip = "true" } \
    /<propval.*password/ && (pconf == "user") { \
        sub(/value="/, "&" up); if (up == "") skip = "true" } \
    /<propval.*password/ && (pconf == "root") { \
        sub(/value="/, "&" rp); if (rp == "") skip = "true" } \
    /<propval.*description/ { \
        sub(/value="/, "&" desc); if (desc == "") skip = "true" } \
    /<propval.*timezone/ { \
        sub(/value="/, "&" tz); if (tz == "") skip = "true" } \
    /<propval.*hostname/ { \
        sub(/value="/, "&" nn); if (nn == "") skip = "true" } \
    { if (skip == "false") print}' \
    login="$username" up="$userpass" desc="$description" rp="$rootpass" \
    tz="$timezone" nn="$nodename" \
    "$MANIFEST_TMP" > "$manifest_new"

if (( $? != 0 )) ; then
	error_exit "Failed to create target ai manifest $manifest_new."
fi

# remove temporary file
rm $MANIFEST_TMP

if (( $? != 0 )) ; then
	error_exit "Failed to remove temporary file $MANIFEST_TMP."
fi

exit 0

