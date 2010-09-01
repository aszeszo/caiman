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
# Copyright (c) 2009, 2010, Oracle and/or its affiliates. All rights reserved.
#


'''Set "_" to be the character that flags text that should be
extracted by xgettext for translation"

Set the ESCDELAY environment variable, if it's not yet set
(n)curses will wait ESCDELAY milliseconds after receiving an
ESC key as input before processing the input. It defaults to 1000 ms
(1 sec), which causes function and arrow keys to react very slowly, so
we default to 100 instead. (Settings of '0' interfere with tipline
esc-sequences)

'''


import gettext
from os import environ

_ = gettext.translation("textinstall", "/usr/share/locale",
                        fallback=True).ugettext
LOG_LOCATION_FINAL = "/var/sadm/system/logs/install_log"
DEFAULT_LOG_LOCATION = "/tmp/install_log"
DEFAULT_LOG_LEVEL = "info"
DEBUG_LOG_LEVEL = "debug"
LOG_FORMAT = ("%(asctime)s - %(levelname)-8s: "
              "%(filename)s:%(lineno)d %(message)s")
LOG_LEVEL_INPUT = 5
LOG_NAME_INPUT = "INPUT"
RELEASE = {"release" : _("Oracle Solaris"),
           "getting-started" : "opensolaris.com/use"}

environ.setdefault("ESCDELAY", "200")
