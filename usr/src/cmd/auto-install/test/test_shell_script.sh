#!/usr/bin/bash

pfexec cp -f ${SRC}/cmd/auto-install/test/profile_auto_reboot_true.xml /var/run/manifest.xml

exit $?
