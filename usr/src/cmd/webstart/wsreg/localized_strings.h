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
 * Copyright 2003 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _LOCALIZED_STRINGS_H
#define	_LOCALIZED_STRINGS_H


#ifdef __cplusplus
extern "C" {
#endif

#include <libintl.h>

/*
 * Strings to be localized
 */
#define	PRODREG_NO_STAT dgettext(TEXT_DOMAIN, \
	"Could not determine the location of the prodreg GUI program file.")
#define	PRODREG_NO_PROG dgettext(TEXT_DOMAIN, \
	"Could not find prodreg GUI program: " PRODREG_GUI)
#define	PRODREG_USAGE_TEXT dgettext(TEXT_DOMAIN, \
	"Use `prodreg --help` for help.")
#define	PRODREG_NO_EXEC dgettext(TEXT_DOMAIN, \
	"Could not execute prodreg GUI program: " PRODREG_GUI)
#define	PRODREG_UNREGISTER dgettext(TEXT_DOMAIN, \
	"Could not unregister the component.")
#define	PRODREG_NOT_UNREGABLE dgettext(TEXT_DOMAIN, \
	"Could not unregister this component.  It isn't actually registered.")
#define	PRODREG_UNREG_WOULD_BREAK dgettext(TEXT_DOMAIN, \
	"Could not unregister.  The component is depended upon " \
	"by other software:")
#define	PRODREG_UNINSTALL_IMPOSSIBLE dgettext(TEXT_DOMAIN, \
	"Could not uninstall the component as requested.  Only registered " \
	"components\ncan be uninstalled.")
#define	PRODREG_UNINSTALL_WOULD_BREAK dgettext(TEXT_DOMAIN, \
	"Could not uninstall.  The component is depended upon " \
	"by other software:")
#define	PRODREG_COMPLETE_DEPENDENCIES dgettext(TEXT_DOMAIN, \
	"The complete list of dependencies of the component or the " \
	"components dependencies is:")
#define	PRODREG_CANNOT_WRITE dgettext(TEXT_DOMAIN, \
	"Cannot obtain write privileges to the registry.  " \
	"Try again as root.")
#define	PRODREG_CONVERT_NEEDED_ACCESS dgettext(TEXT_DOMAIN, \
	"Cannot access the product registry.  It may need to be upgraded.\n" \
	"Please refer to user documentation.")
#define	PRODREG_CANNOT_READ dgettext(TEXT_DOMAIN, \
	"Initialization failed. Cannot obtain read privileges to the " \
	"registry.")
#define	PRODREG_INIT dgettext(TEXT_DOMAIN, \
	"Initialization failed.")
#define	PRODREG_NO_SUCH_COMPONENT dgettext(TEXT_DOMAIN, \
	"The component requested could not be found.")
#define	PRODREG_AMBIGUOUS_RESULTS dgettext(TEXT_DOMAIN, \
	"The request failed because multiple components correspond " \
	"to the criteria given.\nUse the list of possible components " \
	"given below, select one and try again.")
#define	PRODREG_FAILED dgettext(TEXT_DOMAIN, \
	"The requested command failed.")
#define	PRODREG_MALLOC dgettext(TEXT_DOMAIN, \
	"The operation could not allocate sufficient memory.")
#define	INSTALLER_NO_PROG dgettext(TEXT_DOMAIN, \
	"The install program requested could not be found.")
#define	INSTALLER_NO_STAT dgettext(TEXT_DOMAIN, \
	"The install program requested could not be accessed.")
#define	INSTALLER_NO_EXEC dgettext(TEXT_DOMAIN, \
	"The install program requested could not be executed.")
#define	PRODREG_BAD_COMMAND dgettext(TEXT_DOMAIN, \
	"Don't understand bad command \"%s\"")
#define	PRODREG_BAD_SYNTAX dgettext(TEXT_DOMAIN, \
	"The command line could not be understood.")
#define	PRODREG_BAD_PARAMETER dgettext(TEXT_DOMAIN, \
	"Parameter \"%s\" not understood.")
#define	PRODREG_NO_UNINSTALLER dgettext(TEXT_DOMAIN, \
	"The uninstaller could not be found.")
#define	PRODREG_USE_HELP dgettext(TEXT_DOMAIN, \
	"\nUse `prodreg --help` for help.")
#define	PRODREG_VERSION dgettext(TEXT_DOMAIN, \
	"3.1.0")
#define	PRODREG_REGISTER_PARAM_BAD dgettext(TEXT_DOMAIN, \
	"Error: prodreg register %s parameter bad '%s'\n")
#define	PRODREG_REGISTER_FAILED dgettext(TEXT_DOMAIN, \
	"Error: prodreg register failed.")

#define	PRODREG_HELP_USAGE dgettext(TEXT_DOMAIN, \
	"Usage: %s SUBCOMMAND ARGUMENTS...\n" \
	"command subcommand arguments\n" \
	"prodreg            [-R altroot]\n" \
	"prodreg awt        [-R altroot]\n" \
	"prodreg browse     [-R altroot] -m <name>\n" \
	"prodreg browse     [-R altroot] -n <bnum>\n" \
	"prodreg browse     [-R altroot] " \
	"[-u <uuid> [-i <instance>]]\n" \
	"prodreg --help\n" \
	"prodreg -?\n" \
	"prodreg info       [-R altroot] " \
	"-n <bnum> [-R altroot] [(-a <attr> | -d)]\n" \
	"prodreg info       [-R altroot] " \
	"-m <name> [(-a <attr> | -d)]\n" \
	"prodreg info       [-R altroot] " \
	"-u <uuid> [-i <instance>] [(-a <attr>)| -d)]\n" \
	"prodreg swing      [-R altroot] \n" \
	"prodreg uninstall  [-R altroot] " \
	"[-f] -u <uuid> (-p <location> | -i <instance>) ARGS...\n" \
	"prodreg uninstall  [-R altroot] <mnemonic> <location> ARGS...\n" \
	"prodreg unregister [-R altroot] " \
	"[-fr] -u <uuid> [(-p <location> | -i <instance>)]\n" \
	"prodreg unregister [-R altroot] <mnemonic> [<location>]\n" \
	"prodreg --version\n" \
	"prodreg -V\n\n" \
	"For more information, see prodreg(1M).")
#define	PRODREG_HELP dgettext(TEXT_DOMAIN, \
	"Usage: prodreg SUBCOMMAND ARGUMENTS...\n" \
	"Administer and examine the Solaris Product Registry.\n" \
	"  prodreg [-R <root>]  Start the default prodreg GUI.\n" \
	"  prodreg awt          Start a Java awt GUI.\n" \
	"  prodreg browse       Browse the Registry.\n" \
	"  prodreg info         Examine the attributes of an entry " \
	"in the Registry.\n" \
	"  prodreg help         Output this list.\n" \
	"  prodreg --help       Output this list.\n" \
	"  prodreg -?           Output this list.\n" \
	"  prodreg swing        Start a Java swing GUI.\n" \
	"  prodreg version      Output the version string.\n" \
	"  prodreg --version    Output the version string.\n" \
	"  prodreg -V           Output the version string.\n" \
	"  prodreg unregister   Unregister an entry in the registry.\n" \
	"  prodreg uninstall    Start an uninstaller registered with " \
	"installed software.\n" \
	"\nFor more information, see prodreg(1M).")
#define	PRODREG_HELP_AWT dgettext(TEXT_DOMAIN, \
	"Usage: prodreg awt [-R <root>]\n" \
	"This launches a Java AWT based prodreg graphical user " \
	"interface.\n\n" \
	"  -R <root>       An alternate root for the product registry " \
	"database.\n" \
	"\nFor more information, see prodreg(1M).")
#define	PRODREG_HELP_BROWSE dgettext(TEXT_DOMAIN, \
	"Usage: prodreg browse [-R <root>] (-u <uuid> " \
	"[-i <instance> | -p <location>] |\n" \
	"                                   -n <bnum> " \
	"[-i <instance> | -p <location>] |\n" \
	"                                   -m <name> )]\n" \
	"Browse the Solaris Install Registry.  The ancestry of the " \
	"component and\n" \
	"its children are listed, along with each components " \
	"bnum, uuid,\n" \
	"instance number and name.  If a 'prodreg browse' " \
	"request is ambiguous,\n" \
	"because the <uuid> given refers to more than one " \
	"instance, or because\n" \
	"the <name> refers to more than one component, the " \
	"list of components\n" \
	"which could have been referred to is returned.\n\n" \
	"Start by browsing the root of the Registry with " \
	"\"prodreg browse\".  Select \n" \
	"components to expand.  Use browse numbers as a convenience " \
	"during this \n" \
	"interactive browsing, but not in scripts, as they may change " \
	"from one session \n" \
	"to the next.  Browse numbers are generated as they are first " \
	"used, for a given \n" \
	"user on a particular system.\n\n" \
	"  -i <instance>   Browse the particular installed " \
	"component instance.\n" \
	"  -u <uuid>       Browse the component with the " \
	"given unique id.\n" \
	"  -m <name>       Browse the named component.\n" \
	"  -n <bnum>       Browse the component indicated by <bnum>.\n" \
	"  -R <root>       An alternate root for the product registry " \
	"database.\n" \
	"\nFor more information, see prodreg(1M).")
#define	PRODREG_HELP_INFO dgettext(TEXT_DOMAIN, \
	"Usage: prodreg info [-R <root>] (-u <uuid> " \
	"[-i <instance> | -p <location>] |\n" \
	"                                 -n <bnum> " \
	"[-i <instance> | -p <location>] |\n" \
	"                                 -m <name> )]\n" \
	"                                  [(-a <attr> | -d )]\n" \
	"Display attribute information associated with a component " \
	"in the Solaris\n" \
	"Install Registry.  All attributes are shown unless a specific " \
	"attribute\n" \
	"name is requested, or '-d' queries whether the component is " \
	"'damaged.'\n" \
	"If a 'prodreg info' request is ambiguous, because the <uuid> " \
	"or bnum given\n" \
	"refers to more than one instance, or because the <name> refers " \
	"to more than one\n" \
	"component, the list of components which could have been " \
	"referred to is\n" \
	"returned.\n\n" \
	"  -i <instance>   Specifies an installed instance of a " \
	"component.\n" \
	"  -u <uuid>       Specifies a component to display info of.\n" \
	"  -m <name>       Gives the name of a component to display info " \
	"of.\n" \
	"  -n <bnum>       Gives the number used to browse a " \
	"component.\n" \
	"  -a <attr>       If given, return info on the specified " \
	"attribute only.\n" \
	"  -d              If given, return only whether a component " \
	"is damaged.\n" \
	"  -R <root>       An alternate root for the product registry " \
	"database.\n" \
	"\nFor more information, see prodreg(1M).")
#define	PRODREG_HELP_LIST dgettext(TEXT_DOMAIN, \
	"Usage: %s list [-R root] <fld> " \
	"<fld> <fld> [<fld>...]\n" \
	"This is an archaic prodreg 2.0 command used to list attributes.\n" \
	"The attributes will only be listed if the attribute <fld> is \n" \
	"supported by a particular component (with any value).\n" \
	"\nEach <fld> can be any of the following: \n" \
	"    mnemonic    The unique name\n" \
	"    version     The version string\n" \
	"    vendor      The vendor string\n" \
	"    installlocation  The location\n" \
	"    title       The display name, as 'name' in prodreg cli.\n" \
	"    uninstallprogram  The location of the uninstaller.\n" \
	"    OTHER       Any additional attribute value.\n" \
	"\nClean up scripts used 'prodreg list mnemonic mnemonic id'\n" \
	"There is no way to view the value of the UUID, aka 'id'.\n" \
	"Use 'prodreg info' and 'prodreg browse';  " \
	"this feature is deprecated.")
#define	PRODREG_HELP_SWING dgettext(TEXT_DOMAIN, \
	"Usage: prodreg swing [-R <root>]\n" \
	"This launches a Java Swing based prodreg graphical user " \
	"interface.\n\n" \
	"  -R <root>       An alternate root for the product registry " \
	"database.\n" \
	"\nFor more information, see prodreg(1M).")
#define	PRODREG_HELP_UNREGISTER dgettext(TEXT_DOMAIN, \
	"Usage: prodreg unregister [-R <root>] (<mnemonic> " \
	"<info> |\n" \
	"                                       [-fr] -u <uuid> -p " \
	"<location>|\n" \
	"                                       [-fr] -u <uuid> -i " \
	"<instance>)\n" \
	"This removes a component from the registry.\n" \
	"Caution is required when using the -r and -f options.\n\n" \
	"  <mnemonic>      An obsolete identifier for registered " \
	"component types.\n" \
	"                  The mnemonic is really the 'unique name'" \
	"attribute.\n" \
	"                  Components are unregistered recursively.\n" \
	"  <info>          An obsolete representation of install " \
	"location, id attribute\n" \
	"                  or '-' wild card.\n" \
	"  -f              This forces the operation even if damage " \
	"will result.\n" \
	"                  This option also unregisters all instances " \
	"even if <uuid>\n" \
	"                  is ambiguous.\n" \
	"  -r              This causes a recursive unregistration of " \
	"a  component\n" \
	"                  as well as that component's children and " \
	"dependencies.\n" \
	"  -R <root>       An alternate root for the product registry " \
	"database.\n" \
	"  -u <uuid>       This identifies a component type to " \
	"unregister.\n" \
	"  -p <location>   This specifies the location of a " \
	"component to unregister.\n" \
	"  -i <instance>   This specifies the instance of a component " \
	"to unregister.\n\n" \
	"For more information, see prodreg(1M).")
#define	PRODREG_HELP_UNINSTALL dgettext(TEXT_DOMAIN, \
	"Usage: prodreg uninstall ([-R <root>] <mnemonic> " \
	"<info> [ARGS...] |\n" \
	"                          [-R <root>] [-f] -u <uuid> " \
	"-p <location> [ARGS...] |\n" \
	"                          [-R <root>] [-f] -u <uuid> -i " \
	"<instance> [ARGS...])\n" \
	"Launches an uninstaller referred to by a registered " \
	"component or by its\n" \
	"absolution location.  Additional arguments are passed to " \
	"the installer.\n" \
	"Uninstall will not be performed if it is determined that " \
	"it would damage\n" \
	"a dependent component.\n\n" \
	"  <mnemonic>      An obsolete identifier for registered " \
	"component types.\n" \
	"  <info>          An obsolete specifier of install " \
	"location or id attribute.\n" \
	"  -f              This forces the operation even if damage " \
	"will result.\n" \
	"  -u <uuid>       This identifies a component type to " \
	"uninstall.\n" \
	"  -p <location>   This specifies the location of a " \
	"component to uninstall.\n" \
	"  -i <instance>   This specifies the instance of a " \
	"component to uninstall.\n" \
	"  -R <root>       An alternate root for the product registry " \
	"database.\n" \
	"  ARGS            These arguments are passed to the " \
	"uninstaller.\n\n" \
	"For more information, see prodreg(1M).")

#define	PRODREG_HELP_REGISTER dgettext(TEXT_DOMAIN, \
	"Usage: prodreg register -u <uuid> [optional]\n" \
	"Registers a component given on the command line.\n\n" \
	"Optional arguments include:\n" \
	"  [-b backward-compatible-version ] (zero or more)\n" \
	"  [-c child-uuid '{' instance# '}' '{' version '}' ] " \
	"(zero or more)\n" \
	"  [-d dependent-uuid '{' instance# '}' '{' version '}' ] " \
	"(zero or more)\n" \
	"  [-D attribute '{' value '}' ] (zero or more)\n" \
	"  [-n display-name '{' language-tag '}' ] (zero or more)\n" \
	"  [-p location ] (one, zero is *not a good idea*)\n" \
	"  [-P parent-uuid '{' instance# '}' '{' version '}' ] " \
	"(zero or one)\n" \
	"  [-r required-uuid '{' instance# '}' '{' version '}' ] " \
	"(zero or more)\n" \
	"  [-R alt_root ] (zero or one)\n" \
	"  [-t (PRODUCT | FEATURE | COMPONENT) ] default: COMPONENT " \
	"(zero or one)\n" \
	"  [-U unique-name ] (zero or one)\n" \
	"  [-v prod-version ] (one, zero is *not a good idea*)\n" \
	"  [-V vendor-string ] (zero or one)\n" \
	"  [-x uninstaller-command ] (zero or one)\n\n" \
	"This command is not listed in the man page prodreg(1M) as it is " \
	"only supported\n" \
	"as a Private interface.  It is therefore not supported externally." \
	"\nFor an explanation of supported interface categories " \
	"see attributes(5).")

#define	PRODREG_TITLE dgettext(TEXT_DOMAIN, "Title")
#define	PRODREG_VERSIONT dgettext(TEXT_DOMAIN, "Version")
#define	PRODREG_LOCATION dgettext(TEXT_DOMAIN, "Location")
#define	PRODREG_UNINAME dgettext(TEXT_DOMAIN, "Unique Name")
#define	PRODREG_VENDOR dgettext(TEXT_DOMAIN, "Vendor")
#define	PRODREG_UNINSTPROG dgettext(TEXT_DOMAIN, "Uninstall Program")
#define	PRODREG_SUPLANG dgettext(TEXT_DOMAIN, "Supported Languages")
#define	PRODREG_CHILCOMP dgettext(TEXT_DOMAIN, "Child Components")
#define	PRODREG_REQCOMP dgettext(TEXT_DOMAIN, "Required Components")
#define	PRODREG_PARCOMP dgettext(TEXT_DOMAIN, "Parent Component")
#define	PRODREG_DEPCOMP dgettext(TEXT_DOMAIN, "Dependent Components")

#define	PRODREG_LISTHEAD dgettext(TEXT_DOMAIN, \
	"Name                                   UUID"\
	"                                  #\n" \
	"-------------------------------------  "\
	"------------------------------------  --")

#define	PRODREG_BH dgettext(TEXT_DOMAIN, \
	"BROWSE #    +/-/.   UUID                                "\
	"   #  NAME\n"\
	"========  ========  ===================================="\
	"  ==  ===================\n")

#define	REGCONVERT_COMPLETE dgettext(TEXT_DOMAIN, "regconvert converted %d " \
	"articles.")
#define	REGCONVERT_FILE_NOT_FOUND dgettext(TEXT_DOMAIN, "%s: No such file")
#define	REGCONVERT_PERMISSION_DENIED dgettext(TEXT_DOMAIN, "%s not " \
	"converted: Permission denied")
#define	REGCONVERT_BAD_REG_PERMISSION dgettext(TEXT_DOMAIN, "%s not " \
	"converted: Registry write access denied")
#define	REGCONVERT_UNRECOGNIZED_FAILURE dgettext(TEXT_DOMAIN, "%s not " \
	"converted: unrecognized return code %d")
#define	REGCONVERT_NO_CONVERSION_REQUIRED dgettext(TEXT_DOMAIN, "registry " \
	"conversion not required")
#define	REGCONVERT_PROGRESS dgettext(TEXT_DOMAIN, "converting . . . %3d%% " \
	"complete")
#define	REGCONVERT_USAGE dgettext(TEXT_DOMAIN, "usage: regconvert [-R " \
	"alternate_root] [-f registry_file] [-b]")
#define	REGCONVERT_BAD_REGISTRY_FILE dgettext(TEXT_DOMAIN, "bad registry " \
	"file %s")
#define	REGCONVERT_CANT_CREATE_TMP_DIR dgettext(TEXT_DOMAIN, "could not " \
	"create temporary directory for the registry conversion")
#define	REGCONVERT_NO_UNZIP dgettext(TEXT_DOMAIN, "%s not converted: the " \
	"unzip binary is not installed in /usr/bin")
#define	REGCONVERT_COULDNT_UNZIP dgettext(TEXT_DOMAIN, "%s not converted: " \
	"could not unzip the registry file %s")

#define	WSREG_OUT_OF_MEMORY dgettext(TEXT_DOMAIN, "out of memory")
#define	WSREG_SYSTEM_SOFTWARE dgettext(TEXT_DOMAIN, "%s %s System Software")

#ifdef	__cplusplus
}
#endif

#endif /* _LOCALIZED_STRINGS_H */
