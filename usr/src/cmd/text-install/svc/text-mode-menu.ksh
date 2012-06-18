#!/bin/ksh93
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
# Copyright (c) 2009, 2012, Oracle and/or its affiliates. All rights reserved.
#

LANGUAGE_FILE=/etc/sysconfig/language

export TEXTDOMAINDIR="/usr/share/locale"
export TEXTDOMAIN="solaris_install_text_menu"
# LOGNAME variable is needed to display the shell prompt appropriately
export LOGNAME=root

# Block all signals which could terminate the menu or return to a parent process
trap "" TSTP INT TERM ABRT QUIT

# Determine which shell program to use by grabbing this user's login-shell
# from /etc/passwd
ROOT_SHELL=$(/usr/bin/getent passwd $LOGNAME |/usr/bin/cut -d':' -f7)

# On the off chance that $LOGNAME has no shell (default grabbed from passwd(4))
if [[ -z "$ROOT_SHELL" ]]; then
	ROOT_SHELL="/usr/bin/sh"
fi

# Define the menu of commands and prompts
menu_items=( \
    (menu_str=`gettext "Install Oracle Solaris"`			 \
	cmds=("/usr/bin/text-install")					 \
	do_subprocess="true"						 \
	msg_str="")							 \
    (menu_str=`gettext "Install Additional Drivers"`			 \
	cmds=("/usr/bin/ddu-text")					 \
	do_subprocess="true"						 \
	msg_str="")							 \
    (menu_str=`gettext "Shell"`						 \
	cmds=("$ROOT_SHELL")						 \
	do_subprocess="true"						 \
	msg_str=`gettext "To return to the main menu, exit the shell"`)	 \
    # this string gets overwritten every time $TERM is updated
    (menu_str_form=`gettext "Terminal type (currently %s)"`		 \
	menu_str=`printf "${menu_str_form}" "$TERM"`                     \
	cmds=("prompt_for_term_type")					 \
	do_subprocess="false"						 \
	msg_str="")							 \
    (menu_str=`gettext "Reboot"`					 \
	cmds=("/usr/sbin/reboot" "/usr/bin/sleep 10000")		 \
	do_subprocess="true"						 \
	msg_str="")							 \
)

# Update the menu_str for the terminal type
# entry. Every time the terminal type has been
# updated, this function must be called.
function update_term_menu_str
{
    # update the menu string to reflect the current TERM
    for i in "${!menu_items[@]}"; do
	    if [[ "${menu_items[$i].cmds[0]}" = "prompt_for_term_type" ]] ; then
		menu_str_form=`gettext "Terminal type (currently %s)"`
		menu_items[$i].menu_str=`printf "${menu_str_form}" "$TERM"`
	    fi
    done
}

# Set the TERM variable as follows:
#
# If connected to SPARC via keyboard/monitor, set TERM to "sun"
# If connected to X86 via keyboard/monitor, set TERM to "sun-color"
# If running on serial console, set TERM to "xterm"
#
function set_term_type
{
    export TERM=xterm
    arch=`/usr/bin/uname -p`
    if [[ "${arch}" = "sparc" ]] ; then
	output_device=`/usr/sbin/prtconf -vp | 			\
		/usr/bin/grep "output-device" | 		\
		/usr/bin/cut -f 2 -d\'`
	[[ "$output_device" = "screen" ]] && export TERM=sun
    else
	console=`/usr/sbin/prtconf -vp | 			\
		/usr/bin/grep "console" |			\
		/usr/bin/cut -f 2 -d\'`
	[[ -z ${console} ]] && export TERM=sun-color
    fi
    update_term_menu_str
}

# Prompt the user for terminal type
function prompt_for_term_type
{
	integer i

	# list of suggested termtypes
	typeset termtypes=(
		typeset -a fixedlist
		integer list_len        # number of terminal types
	)

	# hard coded common terminal types
	termtypes.fixedlist=(
		[0]=(  name="dtterm"	desc=`gettext "CDE terminal emulator"`)
		[1]=(  name="xterm"	desc="xterm"		    )
		[2]=(  name="vt100"	desc="DEC VT100"	    )
	)

	termtypes.list_len=${#termtypes.fixedlist[@]}

	# Start with a newline before presenting the choices
	print
	printf "`gettext \"Indicate the type of terminal being used, such as:\"`\n"

	# list suggested terminal types
	for (( i=0 ; i < termtypes.list_len ; i++ )) ; do
		nameref node=termtypes.fixedlist[$i]
		printf "  %-10s %s\n" "${node.name}" "${node.desc}"
	done

	print
	# Prompt user to select terminal type and check for valid entry
	typeset term=""
	while true ; do
		menu_str_form=`gettext "Enter Terminal type [%s]: "`
		menu_str=`printf "${menu_str_form}" "$TERM"`
		read "term?${menu_str}" || continue

		# if the user just hit return, don't set the term variable
		[[ "${term}" = "" ]] && return
			
		# check if the user specified option is valid
		term_entry=`/usr/bin/ls /usr/gnu/share/terminfo/*/$term 2> /dev/null`
		[[ ! -z ${term_entry} ]] && break
		printf "`gettext \"\\\"%s\\\" terminal type not supported.\"` \n" "${term}"
		printf "`gettext \"Supported terminal types can be found by using the Shell to list the contents of /usr/gnu/share/terminfo.\"`\n\n"
	done

	export TERM="${term}"
	update_term_menu_str
}

set_term_type

# Set LANG to the language specified in /etc/sysconfig/language
if [ -f ${LANGUAGE_FILE} ] ; then
    language=`grep RC_LANG ${LANGUAGE_FILE} | cut -d '=' -f 2`
    if [ ! -z ${language} ] ; then
	export LANG=$language
    fi
fi

# default to the Installer option
defaultchoice=1

for ((;;)) ; do

	# Display the menu.
	clear
	printf \
	    "`gettext 'Welcome to the Oracle Solaris installation menu'`"
	printf " \n\n"
	for i in "${!menu_items[@]}"; do
		print "\t$((${i} + 1))  ${menu_items[$i].menu_str}"
	done

	# Take an entry (by number). If multiple numbers are
 	# entered, accept only the first one.
	input=""
	dummy=""
	print -n "\n`gettext 'Please enter a number '`""[${defaultchoice}]: "
	read input dummy 2>/dev/null

	# If no input was supplied, select the default option
	[[ -z ${input} ]] && input=$defaultchoice

	# First char must be a digit.
	if [[ ${input} =~ [^1-9] || ${input} > ${#menu_items[@]} ]] ; then
		continue
	fi

	# Reorient to a zero base.
	input=$((${input} - 1))

	nameref msg_str=menu_items[$input].msg_str

	# Launch commands as a subprocess.
	# However, launch the functions within the context 
	# of the current process.
	if [[ "${menu_items[$input].do_subprocess}" = "true" ]] ; then
		(
		trap - TSTP INT TERM ABRT QUIT
		# Print out a message if requested
		[[ ! -z "${msg_str}" ]] && printf "%s\n" "${msg_str}"
		for j in "${!menu_items[$input].cmds[@]}"; do
			${menu_items[${input}].cmds[$j]}
		done
		)
	else
		# Print out a message if requested
		[[ ! -z "${msg_str}" ]] && printf "%s\n" "${msg_str}"
		for j in "${!menu_items[$input].cmds[@]}"; do
			${menu_items[${input}].cmds[$j]}
		done
	fi
done
