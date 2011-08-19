#!/usr/bin/python2.6
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

'''Main launcher for Automated Installer'''

import sys
from solaris_install.auto_install import auto_install

if __name__ == '__main__':
    try:
        ai = auto_install.AutoInstall(sys.argv[1:])
        ai.perform_autoinstall()
        sys.exit(ai.exitval)

    except Exception, e:
        print "ERROR: an exception occurred.\n"
        print "\n".join(["%s%s" % ("    ", l)  for l in str(e).splitlines()])
        print "\nPlease check logs for futher information."
        sys.exit(auto_install.AutoInstall.AI_EXIT_FAILURE)
    except KeyboardInterrupt:
        pass
