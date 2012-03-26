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
# Copyright (c) 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Representation of OCM and ASR services on the system
'''

import errno
import fcntl
import logging
import os
import tempfile
import time

import solaris_install.data_object as data_object

from solaris_install import CalledProcessError, Popen, run, SYSTEM_TEMP_DIR
from solaris_install.sysconfig import _
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig.profile import SMFConfig, SMFInstance, \
                                              SMFPropertyGroup, \
                                              SMFProperty, SUPPORT_LABEL

CONV_NONE = lambda strg: None if not strg else str(strg)
CONV_EMPTY = lambda strg: "" if not strg else str(strg)

_LOGGER = None


def LOGGER():
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = logging.getLogger(INSTALL_LOGGER_NAME + ".sysconfig")
    return _LOGGER


def _current_net_exists():
    '''Return True/False that system is on a network.
    '''
    argslist = ['/usr/sbin/ipadm', 'show-addr', '-p', '-o',
                'addrobj,state,current']
    try:
        ipadm_out = run(argslist, logger=LOGGER())
    except CalledProcessError:
        LOGGER().error("current_net_exists(): Error calling ipadm")
        raise

    lines = ipadm_out.stdout.splitlines()
    filtered = [line for line in lines if not line.startswith("lo") and
        ":ok:U" in line]
    return len(filtered) >= 1


def _write_tempfile(contents):
    '''Write a file containing the string passed in as an argument.

    Uses the secure way of writing files, so is well-suited for passwords and
    sensitive data.
    '''
    (fd, filename) = tempfile.mkstemp(dir=SYSTEM_TEMP_DIR)
    os.write(fd, contents)
    os.close(fd)
    return filename


def _fork_proc(cmd, timeout=15):
    '''Run a command in a forked process, with a timeout.

    Kills the process on timeout.
    Logs errors.
    Handles processes with large amounts of data so check_call() is not used.

    Args:
      - cmd: a list of commandline arguments
      - timeout: timeout in seconds
    Returns:
      - Return status:
        - return status of the command run, if command completes.
        - SupportInfo.PH_TIMEOUT if timeout occurs.
      - stdout and stderr of the run process.
    '''
    timeout_tenths = timeout * 10

    def read_subproc(subproc, outbuf, errbuf):
        intoutbuf = interrbuf = ""
        try:
            intoutbuf = subproc.stdout.read()
            outbuf = "".join([outbuf, intoutbuf])
        except IOError as err:
            if err.errno != errno.EAGAIN:
                raise
        try:
            interrbuf = subproc.stderr.read()
            errbuf = "".join([errbuf, interrbuf])
        except IOError as err:
            if err.errno != errno.EAGAIN:
                raise
        return (outbuf, errbuf)

    # Can throw an child_exception if command cannot be started.
    subproc = Popen(cmd, stdout=Popen.PIPE, stderr=Popen.PIPE)

    flags = fcntl.fcntl(subproc.stdout.fileno(), fcntl.F_GETFL)
    fcntl.fcntl(subproc.stdout.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)
    flags = fcntl.fcntl(subproc.stderr.fileno(), fcntl.F_GETFL)
    fcntl.fcntl(subproc.stderr.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)

    (outbuf, errbuf) = read_subproc(subproc, "", "")
    while subproc.poll() is None and timeout_tenths > 0:
        timeout_tenths -= 1
        time.sleep(0.1)
        (outbuf, errbuf) = read_subproc(subproc, outbuf, errbuf)
    if subproc.returncode is None:
        subproc.terminate()
        return (SupportInfo.PH_TIMEOUT, outbuf, errbuf)
    else:
        (outbuf, errbuf) = read_subproc(subproc, outbuf, errbuf)
    return (subproc.returncode, outbuf, errbuf)


class SupportInfo(data_object.DataObject):
    '''Represents OCM and ASR service configuration'''

    LABEL = SUPPORT_LABEL

    # Default email filled in.
    UNAUTH_EMAIL = "anonymous@oracle.com"

    # netcfg settings.  These direct which screens show.
    # DIRECT, PROXY and HUB are overloaded to represent the phone_home mode too
    DIRECT = "DIRECT"   # No proxy or hub screens needed.  Main screen only.
    PROXY = "PROXY"     # Turns on Proxy Screen.
    HUB = "HUB"         # Turns on Hub screen.
    NOSVC = "0"         # Neither OCM nor ASR installed.  Do nothing.
                        #   Let OCM and ASR services take their defaults when
                        #     they are installed in the future.
    NOCFGNET = "1"      # No future net configured.
                        #   Store blank MOS credentials and skip screens.

    MSGS = {
        "pswd_no_email": _("Cannot specify a password without an "
                           "email address."),
        "no_email": _("Warning: No email address provided."),
        "missing_@": _("Missing or misplaced '@' in email address."),
        "ocm_timeout": _("OCM timeout contacting Oracle"),
        "ocm_bad_cred": _("Error: Credentials did not validate for OCM."),
        "ocm_net_err": _("Could not contact Oracle to authenticate OCM."),
        "ocm_encr_err": _("OCM cannot encrypt and save password."),
        "ocm_auth_err": _("Internal OCM authentication error."),
        "asr_timeout": _("ASR timeout contacting Oracle"),
        "asr_bad_cred": _("Error: Credentials did not validate for ASR."),
        "asr_net_err": _("Could not contact Oracle to authenticate ASR."),
        "asr_encr_err": _("ASR cannot encrypt and save password."),
        "asr_auth_err": _("Internal ASR authentication error."),
    }

    # Return statuses from OCM authenticator.
    OCM_SUCCESS = 0
    OCM_INTERNAL_ERR = 1
    OCM_USAGE_ERR = 2
    OCM_BAD_CRED = 3
    OCM_NET_ERR = 4

    # No authenticator available.
    OCM_NO_AUTHENTICATOR = 5

    # Could not do encryption.
    OCM_NO_ENCR = 6

    # Return statuses from ASR authenticator.
    ASR_SUCCESS = 0
    ASR_INTERNAL_ERR = 1
    ASR_USAGE_ERR = 2
    ASR_BAD_CONFIG = 3
    ASR_BAD_CRED = 4
    ASR_NET_ERR = 5

    # No authenticator available.
    ASR_NO_AUTHENTICATOR = 6

    # Could not do encryption.
    ASR_NO_ENCR = 7

    # Phone home timeout error (must not conflict w/OCM or ASR return statuses)
    PH_TIMEOUT = 100

    OCM_AUTHENTICATOR = "/usr/lib/ocm/ccr/bin/ocmadm"
    ASR_AUTHENTICATOR = "/usr/sbin/asradm"

    def __init__(self, mos_email=None, mos_password=None, proxy_hostname=None,
        proxy_port=None, proxy_user=None, proxy_password=None,
        ocm_hub=None, asr_hub=None):
        data_object.DataObject.__init__(self, self.LABEL)

        if mos_email is None:
            mos_email = SupportInfo.UNAUTH_EMAIL

        # Treat None as blanks.

        # Visible fields.
        self.mos_email = mos_email
        self.mos_password = mos_password
        self.proxy_hostname = proxy_hostname
        self.proxy_port = proxy_port
        self.proxy_user = proxy_user
        self.proxy_password = proxy_password
        self.ocm_hub = ocm_hub
        self.asr_hub = asr_hub

        # Derived non-visible fields.
        self.ocm_mos_password = None
        self.ocm_index = None
        self.ocm_ciphertext = None
        self.ocm_proxy_password = None
        self.asr_mos_password = None
        self.asr_index = None
        self.asr_private_key = None
        self.asr_public_key = None
        self.asr_client_id = None
        self.asr_timestamp = None
        self.asr_proxy_password = None

        # State, for coordinating screens and validation.

        self.ocm_validated_mos_email = None
        self.asr_validated_mos_email = None

        # System is now on a network
        self.current_net_exists = _current_net_exists()

        # Save which services are available.
        self.ocm_available = os.access(self.OCM_AUTHENTICATOR, os.X_OK)
        self.asr_available = os.access(self.ASR_AUTHENTICATOR, os.X_OK)

        # Default to DIRECT, so installer can start without a proxy or hub
        # specified.
        self.netcfg = SupportInfo.DIRECT

        # Skip all support screens if neither OCM nor ASR exists.
        # In live CD and TI cases, they won't exist on target system either.
        # In AI case, no encryption or authentication can be done without them.
        if (not self.ocm_available and not self.asr_available):
            self.netcfg = SupportInfo.NOSVC
            LOGGER().info("Neither OCM nor ASR service is available.")

    def parse_asradm_output(self, from_asr):
        '''Extract authentication data from ASR authenticator script output.

        Args:
          from_asr: Output from asradm

        Returns:
          key: encryption key used for private_key, password, proxy_password.
          client_id: authentication data if authentication is successful.
          private_key: encrypted authentication data if auth is successful.
          public_key: authentication data if authentication is successful.
          timestamp: authentication data if authentication is successful.
          password: encrypted password.
          proxy_password: encrypted proxy password.
        '''
        key = client_id = private_key = public_key = None
        timestamp = password = proxy_password = None
        LOGGER().debug("asradm returns the following:")
        for line in from_asr.splitlines():
            LOGGER().debug("..." + line)
            parts = line.partition("=")
            if parts[2] == "":
                LOGGER().warning("asradm returned key:%s with missing value" %
                                 (parts[0]))
            elif parts[0] == "index":
                key = parts[2]
            elif parts[0] == "password":
                password = parts[2]
            elif parts[0] == "client-id":
                client_id = parts[2]
            elif parts[0] == "private-key":
                private_key = parts[2]
            elif parts[0] == "public-key":
                public_key = parts[2]
            elif parts[0] == "timestamp":
                timestamp = parts[2]
            elif parts[0] == "proxy-password":
                proxy_password = parts[2]
            elif not (parts[0] == "proxy-user" or parts[0] == "user" or
                      parts[0] == "proxy-host" or parts[0] == "hub-endpoint" or
                      parts[0] == "status"):
                LOGGER().warning("asradm returned unknown key:%s" % parts[0])
        return (key, client_id, private_key, public_key, timestamp, password,
                proxy_password)

    def asr_authenticate(self, mode, encrypt_only=False, proxy_only=False):
        '''Authenticate with the ASR back end.

        Should be called only with a non-blank mos_email and mos_password.

        Args:
          mode: One of DIRECT, PROXY or HUB.
            Used to interpret other arguments.
          encrypt_only: When True, only try to encrypt locally.  Don't connect
            with Oracle.
          proxy_only: When True, only a proxy password is to be encrypted.

        - All fields assumed syntactically valid.

        Returns:
            Authentication status
            (Also modifies instance fields with authorization data.)
        '''
        # For testing with test ASR server.
        if not self.asr_available:
            return self.ASR_NO_AUTHENTICATOR

        if not self.mos_email or (not self.mos_password and not proxy_only):
            return self.ASR_USAGE_ERR

        auth_returncode = self.ASR_SUCCESS
        do_encrypt = False

        # asradm requires a password.  In proxy_only mode there isn't one.
        if proxy_only:
            pswd_filename = _write_tempfile("dummy")
            LOGGER().debug("Wrote dummy password.")

        elif self.asr_mos_password:
            # asr_mos_password is the encrypted password returned from failed
            # earlier authentication. Set up to attempt reauthentication with
            # it if it exists.  Assume key exists when asr_mos_password exists.
            pswd_filename = _write_tempfile(self.asr_mos_password)
            LOGGER().debug("Wrote encr mos password into file %s for asradm" %
                           (pswd_filename))

        else:
            pswd_filename = _write_tempfile(self.mos_password)
            LOGGER().debug("Wrote mos password into file %s for asradm" %
                           (pswd_filename))

        cmd = [self.ASR_AUTHENTICATOR, "authenticate",
               "-u", self.mos_email, "-p", pswd_filename]

        if self.asr_mos_password:
            # Key is assumed present if asr_mos_password is.
            cmd.extend(["-k", self.asr_index])

        if mode == SupportInfo.PROXY:
            if not self.proxy_hostname:
                return self.ASR_USAGE_ERR

            # Combine proxy server and port
            proxy_hostname = self.proxy_hostname.strip()
            if self.proxy_port:
                proxy_hostname = ":".join([proxy_hostname, self.proxy_port])

            cmd.extend(["-h", proxy_hostname])
            if self.proxy_user:
                if not self.proxy_password:
                    return self.ASR_USAGE_ERR
                # Put proxy password in a file.
                ppswd_filename = _write_tempfile(self.proxy_password)
                cmd.extend(["-U", self.proxy_user, "-P", ppswd_filename])

        # Blank hub in hub mode translates into direct mode (no proxy, no hub)
        elif mode == SupportInfo.HUB and self.asr_hub:
            cmd.extend(["-e", self.asr_hub])

        if not encrypt_only:

            # Call up to Oracle via authenticator script.
            LOGGER().debug("ASR authenticate command: " + str(cmd))
            (subproc_stat, subproc_out, subproc_err) = _fork_proc(cmd)

            # If not successful for any reason, generate encrypted passwords.
            # Do so even if credentials are invalid here, because if they are
            # valid for ASR, maybe there's a server problem which will resolve
            # itself later.
            auth_returncode = subproc_stat
            if subproc_stat != self.ASR_SUCCESS:
                LOGGER().error(subproc_err)
                do_encrypt = True

        if encrypt_only or do_encrypt:

            cmd.append("-n")

            LOGGER().debug("ASR encrypt command: " + str(cmd))
            (subproc_stat, subproc_out, subproc_err) = _fork_proc(cmd)
            if subproc_stat != self.ASR_SUCCESS:
                LOGGER().error(subproc_err)
                os.unlink(pswd_filename)
                if self.proxy_user:
                    os.unlink(ppswd_filename)
                return self.ASR_NO_ENCR

        # Break out parameters from the applicable call to asradm.
        # Passwords are overwritten with either None or their encrypted version
        (self.asr_index, client_id, private_key, public_key, timestamp,
         asr_mos_password, self.asr_proxy_password) = \
            self.parse_asradm_output(subproc_out)

        os.unlink(pswd_filename)
        if self.proxy_user:
            os.unlink(ppswd_filename)

        # Save auth data when it won't overwrite a previous authentication.
        if auth_returncode == self.ASR_SUCCESS and not encrypt_only:
            self.asr_public_key = public_key
            self.asr_private_key = private_key
            self.asr_client_id = client_id
            self.asr_timestamp = timestamp
        # Save asr_mos_password only if a real password was given to encrypt.
        if not proxy_only:
            self.asr_mos_password = asr_mos_password

        return auth_returncode

    def check_mos(self, error_override):
        '''Perform common checks on MOS email and password.

        Args:
          error_override: This value can be changed to True before being
            returned, if a failed check is just a warning.

        Returns:
          error_override, possibly set to True.

          message: Error or warning message.

        Raises: N/A
        '''
        message = None

        clear_params = False

        # Clear all credential parameters if email doesn't exist.  Maybe user
        # reconsidered and cleared email after authenticating earlier.
        if not self.mos_email:

            # Error if email is blank but password is not
            if self.mos_password:
                message = SupportInfo.MSGS["pswd_no_email"]
            else:
                clear_params = True
                error_override = True
                message = SupportInfo.MSGS["no_email"]
        else:
            # Set (restore?) unauthenticated mode if no password provided.
            if not self.mos_password:
                clear_params = True

            # Error on invalid email address.
            if '@' not in self.mos_email or self.mos_email[-1] == '@':
                message = SupportInfo.MSGS["missing_@"]

        if clear_params:
            self.mos_password = None
            self.ocm_mos_password = None
            self.ocm_index = None
            self.ocm_ciphertext = None
            self.asr_index = None
            self.asr_mos_password = None
            self.asr_public_key = None
            self.asr_private_key = None

        return (error_override, message)

    def parse_ocmadm_output(self, from_ocm):
        '''Extract authentication data from OCM authenticator script output.

        Args:
          from_ocm: Output from ocmadm

        Returns:
          key: encryption key used for passwords.
          ciphertext: authentication data if authentication is successful.
          password: encrypted password.
          proxy_password: encrypted proxy password.
        '''
        key = ciphertext = password = proxy_password = None
        LOGGER().debug("ocmadm returns the following:")
        for line in from_ocm.splitlines():
            LOGGER().debug("..." + line)
            parts = line.partition("=")
            if parts[2] == "":
                LOGGER().warning("ocmadm returned key:%s with missing value" %
                                 (parts[0]))
            elif parts[0] == "reg/key":
                key = parts[2].strip('"')
            elif parts[0] == "reg/cipher":
                ciphertext = parts[2].strip('"')
            elif parts[0] == "reg/password":
                password = parts[2].strip('"')
            elif parts[0] == "reg/proxy_password":
                proxy_password = parts[2].strip('"')
            elif not (parts[0] == "reg/proxy_username" or
                      parts[0] == "reg/user" or
                      parts[0] == "reg/proxy_host" or
                      parts[0] == "reg/config_hub"):
                LOGGER().warning("ocmadm returned unknown key:%s" % parts[0])
        return (key, ciphertext, password, proxy_password)

    def ocm_authenticate(self, mode, encrypt_only=False, proxy_only=False):
        '''Standin stub for function which authenticates with the OCM back end.

        Should be called only with a non-blank mos_email and mos_password.

        Args:
          mode: One of DIRECT, PROXY or HUB.
            Used to interpret other arguments.
          encrypt_only: When True, only try to encrypt locally.  Don't connect
            with Oracle.
          proxy_only: When True, only a proxy password is to be encrypted.

        - All fields assumed syntactically valid.

        Returns:
            Authentication status
            (Also modifies instance fields with authorization data.)
        '''
        if not self.ocm_available:
            return self.OCM_NO_AUTHENTICATOR

        if not self.mos_email or (not self.mos_password and not proxy_only):
            return self.OCM_USAGE_ERR

        auth_returncode = self.OCM_SUCCESS
        do_encrypt = False

        cmd = [self.OCM_AUTHENTICATOR, "-u", self.mos_email]

        # ocmadm requires a password.  In proxy_only mode there isn't one.
        if proxy_only:
            pswd_filename = _write_tempfile("dummy")
            LOGGER().debug("Wrote dummy password.")
            cmd.extend(["-p", pswd_filename])

        elif self.ocm_mos_password:
            # ocm_mos_password is the encrypted password returned from failed
            # earlier authentication. Set up to attempt reauthentication with
            # it if it exists.  Assume key exists when ocm_mos_password exists.
            pswd_filename = _write_tempfile(self.ocm_mos_password)
            LOGGER().debug("Wrote encr mos password into file %s for ocmadm" %
                           (pswd_filename))
            cmd.extend(["-e", pswd_filename, "-k", self.ocm_index])
        else:
            pswd_filename = _write_tempfile(self.mos_password)
            LOGGER().debug("Wrote mos password into file %s for ocmadm" %
                           (pswd_filename))
            cmd.extend(["-p", pswd_filename])

        if mode == SupportInfo.PROXY:
            if not self.proxy_hostname:
                return self.OCM_USAGE_ERR

            # Combine proxy server and port
            proxy_hostname = self.proxy_hostname.strip()
            if self.proxy_port:
                proxy_hostname = ":".join([proxy_hostname, self.proxy_port])

            cmd.extend(["-r", proxy_hostname])
            if self.proxy_user:
                if not self.proxy_password:
                    return self.OCM_USAGE_ERR
                # Put proxy password in a file.
                ppswd_filename = _write_tempfile(self.proxy_password)
                cmd.extend(["-o", self.proxy_user, "-a", ppswd_filename])

        # If hub field is blank, just use direct mode (no proxy, no hub).
        elif mode == SupportInfo.HUB and self.ocm_hub:
            cmd.extend(["-b", self.ocm_hub])

        # Contact Oracle to do authentication.
        if not encrypt_only:

            # Call up to Oracle via authenticator script.
            LOGGER().debug("OCM authenticate command: " + str(cmd))
            (subproc_stat, subproc_out, subproc_err) = _fork_proc(cmd)

            # If not successful for any reason, generate encrypted passwords.
            # Do so even if credentials are invalid here, because if they are
            # valid for ASR, maybe there's a server problem which will resolve
            # itself later.
            auth_returncode = subproc_stat
            if subproc_stat != self.OCM_SUCCESS:
                LOGGER().error(subproc_err)
                do_encrypt = True

        # Do encryption without having to contact Oracle (again).
        if encrypt_only or do_encrypt:

            # Add -k if not already present and key is available.
            try:
                cmd.index('-k')
            except ValueError:
                if self.ocm_index:
                    cmd.extend(["-k", self.ocm_index])

            cmd.append("-n")
            LOGGER().debug("OCM encrypt command: " + str(cmd))
            (subproc_stat, subproc_out, subproc_err) = _fork_proc(cmd)
            if subproc_stat != self.OCM_SUCCESS:
                LOGGER().error(subproc_err)
                os.unlink(pswd_filename)
                if self.proxy_user:
                    os.unlink(ppswd_filename)
                return self.OCM_NO_ENCR

        # Break out parameters from the applicable call to ocmadm.
        # Passwords are overwritten with either None or their encrypted version
        (self.ocm_index, ciphertext, ocm_mos_password,
         self.ocm_proxy_password) = \
            self.parse_ocmadm_output(subproc_out)

        os.unlink(pswd_filename)
        if self.proxy_user:
            os.unlink(ppswd_filename)

        # Save auth data only when it won't overwrite a previous authentication
        if auth_returncode == self.OCM_SUCCESS and not encrypt_only:
            self.ocm_ciphertext = ciphertext
        # Save ocm_mos_password only if a real password was given to encrypt.
        if not proxy_only:
            self.ocm_mos_password = ocm_mos_password

        return auth_returncode

    @staticmethod
    def phone_home_msg(ocm_status, asr_status):
        ''' Returns a message mapped to statuses returned from phone_home().'''
        message = None
        if ocm_status == SupportInfo.PH_TIMEOUT:
            message = SupportInfo.MSGS["ocm_timeout"]
        elif ocm_status == SupportInfo.OCM_BAD_CRED:
            message = SupportInfo.MSGS["ocm_bad_cred"]
        elif ocm_status == SupportInfo.OCM_NET_ERR:
            message = SupportInfo.MSGS["ocm_net_err"]
        elif ocm_status == SupportInfo.OCM_NO_ENCR:
            message = SupportInfo.MSGS["ocm_encr_err"]
        elif ocm_status != SupportInfo.OCM_SUCCESS:
            message = SupportInfo.MSGS["ocm_auth_err"]

        if not message:
            if asr_status == SupportInfo.PH_TIMEOUT:
                message = SupportInfo.MSGS["asr_timeout"]
            if asr_status == SupportInfo.ASR_BAD_CRED:
                message = SupportInfo.MSGS["asr_bad_cred"]
            elif asr_status == SupportInfo.ASR_NET_ERR:
                message = SupportInfo.MSGS["asr_net_err"]
            elif asr_status == SupportInfo.ASR_NO_ENCR:
                message = SupportInfo.MSGS["asr_encr_err"]
            elif asr_status != SupportInfo.ASR_SUCCESS:
                message = SupportInfo.MSGS["asr_auth_err"]
        return message

    def phone_home(self, mode, force_encrypt_only=False):
        '''Error-check and try to authenticate to Oracle

        Assumes that at least one of OCM or ASR exists.

        Note that fields which are used by both services and are encrypted,
        are processed and stored separately for each service.  For example,
        mos_password and proxy_password are encrypted for each service
        separately and different instances of their encrypted version are
        stored (mos_password) or returned (proxy_password) for each service.

        Args:
          mode can be DIRECT, PROXY or HUB.
          force_enrypt_only: when True, does not do full authentication, but
            only encryption (which is done locally).

        DIRECT: No proxy or hub info is given to OCM or ASR.
        PROXY: Proxy info is used for both OCM and ASR.
        HUB: asr_manager_hub is provided to ASR.
                  ocm_hub is provided to OCM.
                  One hub can be left blank, so one service can connect
                    directly to the internet while the other service uses a hub
                  Neither OCM nor ASR is given a proxy.

        Returns a tuple consisting of:
          ocm_status: Status returned by the OCM authentication script.
          asr_status: Status returned by the ASR authentication script.
        '''
        # Detect the special case of having only to encrypt a proxy password.
        proxy_only = (self.mos_email and self.proxy_password and
                      mode == SupportInfo.PROXY and not self.mos_password)

        # Sanity check.  Only a programming error will cause this.
        if not ((self.mos_email and self.mos_password) or proxy_only):
            raise StandardError("Attempt to authenticate without "
                                "both MOS email and password")

        LOGGER().debug("Attempting to contact Oracle")

        # Attempt authentication only if email has changed, a new mos password
        # is provided, or if authentication failed before (xxx_mos_password is
        # set).

        ocm_status = self.OCM_SUCCESS
        if self.ocm_available:
            LOGGER().debug("Attempting to contact OCM backend")

            # Don't validate mos credentials unless necessary.
            # May need to encrypt locally (to encrypt proxy password after MOS
            # credentials have been processed, for example).
            encrypt_only = (force_encrypt_only or
                            (self.mos_email == self.ocm_validated_mos_email and
                             self.ocm_ciphertext is not None))

            # If encrypt_only is true, only ocm_index and proxy_password
            # will change.  Any user and password will do.  (It doesn't matter
            # that the mos_password may contain stars at this point.)

            ocm_status = self.ocm_authenticate(mode, encrypt_only, proxy_only)
            LOGGER().info("ocm_authenticate returned %d" % ocm_status)

        asr_status = self.ASR_SUCCESS
        if self.asr_available:

            # Don't validate mos credentials unless necessary.
            encrypt_only = (force_encrypt_only or
                            (self.mos_email == self.asr_validated_mos_email and
                             self.asr_private_key is not None))

            asr_status = self.asr_authenticate(mode, encrypt_only, proxy_only)
            LOGGER().info("asr_authenticate returned %d" % asr_status)

        if not proxy_only:
            # Save validated credentials to avoid re-validating again in case
            # proxy changes, etc.  Be mindful of email changes.
            if self.ocm_validated_mos_email:
                # A new email was entered after another had been validated.
                if self.ocm_validated_mos_email != self.mos_email:
                    self.ocm_validated_mos_email = None
            elif ocm_status == self.OCM_SUCCESS:
                self.ocm_validated_mos_email = self.mos_email

            if self.asr_validated_mos_email:
                if self.asr_validated_mos_email != self.mos_email:
                    self.asr_validated_mos_email = None
            elif asr_status == self.ASR_SUCCESS:
                self.asr_validated_mos_email = self.mos_email

        return (ocm_status, asr_status)

    def to_xml(self):
        '''Write SupportInfo object data to XML.

        Write out "None" values as empty strings.
        '''

        # Create no profile data if neither OCM nor ASR services are
        # configured on the system creating the profiles.
        if self.netcfg == SupportInfo.NOSVC:
            LOGGER().debug("SupportInfo.to_xml: NOT creating profile data.")
            return []

        LOGGER().debug("SupportInfo.to_xml: Creating profile data.")

        data_objects = []

        # Set up network configuration variables.  This blocks any entered
        # proxy variables from being put in the profile, if the last thing the
        # user selected was hub, etc.
        phost = puser = ocm_ppassword = asr_ppassword = None
        ocm_hub = asr_hub = None
        if self.netcfg == SupportInfo.PROXY:
            phost = "%s%s%s" % (self.proxy_hostname.strip(), ":",
                                self.proxy_port.strip())
            puser = self.proxy_user
            ocm_ppassword = self.ocm_proxy_password
            asr_ppassword = self.asr_proxy_password
        elif self.netcfg == SupportInfo.HUB:
            ocm_hub = self.ocm_hub
            asr_hub = self.asr_hub

        if self.ocm_available:
            LOGGER().debug("SupportInfo.to_xml: Creating OCM profile data.")
            smf_ocm_svc_config = SMFConfig('system/ocm')
            data_objects.append(smf_ocm_svc_config)
            smf_ocm_svc_config_instance = SMFInstance('default')
            smf_ocm_svc_pg = SMFPropertyGroup('reg')
            smf_ocm_svc_config.insert_children([smf_ocm_svc_config_instance])
            smf_ocm_svc_config_instance.insert_children([smf_ocm_svc_pg])

            # Don't use SMFPropertyGroup add_props() as it doesn't handle
            # dashes in the property names.
            smf_ocm_svc_pg_props = [
                SMFProperty("user", propval=CONV_EMPTY(self.mos_email)),
                SMFProperty("password",
                            propval=CONV_EMPTY(self.ocm_mos_password)),
                SMFProperty("key", propval=CONV_EMPTY(self.ocm_index)),
                SMFProperty("cipher", propval=CONV_EMPTY(self.ocm_ciphertext)),

                SMFProperty("proxy_host", propval=CONV_EMPTY(phost)),
                SMFProperty("proxy_user", propval=CONV_EMPTY(puser)),
                SMFProperty("proxy_password",
                            propval=CONV_EMPTY(ocm_ppassword)),
                SMFProperty("config_hub", propval=CONV_EMPTY(ocm_hub))]
            smf_ocm_svc_pg.insert_children(smf_ocm_svc_pg_props)

        if self.asr_available:
            LOGGER().debug("SupportInfo.to_xml: Creating ASR profile data.")
            smf_asr_svc_config = SMFConfig('system/fm/asr-notify')
            data_objects.append(smf_asr_svc_config)
            smf_asr_svc_config_instance = SMFInstance('default')
            smf_asr_svc_pg = SMFPropertyGroup('autoreg')
            smf_asr_svc_config.insert_children([smf_asr_svc_config_instance])
            smf_asr_svc_config_instance.insert_children([smf_asr_svc_pg])

            smf_asr_svc_pg_props = [
                SMFProperty("user", propval=CONV_EMPTY(self.mos_email)),
                SMFProperty("password",
                            propval=CONV_EMPTY(self.asr_mos_password)),
                SMFProperty("index", propval=CONV_EMPTY(self.asr_index)),
                SMFProperty("private-key",
                            propval=CONV_EMPTY(self.asr_private_key)),
                SMFProperty("public-key",
                            propval=CONV_EMPTY(self.asr_public_key)),
                SMFProperty("client-id",
                            propval=CONV_EMPTY(self.asr_client_id)),
                SMFProperty("timestamp",
                            propval=CONV_EMPTY(self.asr_timestamp)),

                SMFProperty("proxy-host", propval=CONV_EMPTY(phost)),
                SMFProperty("proxy-user", propval=CONV_EMPTY(puser)),
                SMFProperty("proxy-password",
                            propval=CONV_EMPTY(asr_ppassword)),
                SMFProperty("hub-endpoint", propval=CONV_EMPTY(asr_hub))]
            smf_asr_svc_pg.insert_children(smf_asr_svc_pg_props)

        return [do.get_xml_tree() for do in data_objects]

    def __repr__(self):
        result = ["Support Info:"]
        result.append("\n OCM:")
        result.append("\n  MOS Email: ")
        result.append(str(self.mos_email))
        result.append("\n  MOS Password: ")
        result.append(str(self.ocm_mos_password))
        result.append("\n  Proxy hostname: ")
        result.append(str(self.proxy_hostname))
        result.append(", port: ")
        result.append(str(self.proxy_port))
        result.append("\n  Proxy user: ")
        result.append(str(self.proxy_user))
        result.append("\n  Proxy password: ")
        result.append(str(self.ocm_proxy_password))
        result.append("\n  Hub URL: ")
        result.append(str(self.ocm_hub))
        result.append("\n  Index: ")
        result.append(str(self.ocm_index))
        result.append("\n  Ciphertext: ")
        result.append(str(self.ocm_ciphertext))

        result.append("\n ASR:")
        result.append("\n  MOS Email: ")
        result.append(str(self.mos_email))
        result.append("\n  MOS Password: ")
        result.append(str(self.asr_mos_password))
        result.append("\n  Proxy hostname: ")
        result.append(str(self.proxy_hostname))
        result.append(", port: ")
        result.append(str(self.proxy_port))
        result.append("\n  Proxy user: ")
        result.append(str(self.proxy_user))
        result.append("\n  Proxy password: ")
        result.append(str(self.asr_proxy_password))
        result.append("\n  hub URL: ")
        result.append(str(self.asr_hub))
        result.append("\n  Index: ")
        result.append(str(self.asr_index))
        result.append("\n  Private key: ")
        result.append(str(self.asr_private_key))
        result.append("\n  Public key: ")
        result.append(str(self.asr_public_key))
        result.append("\n  client_id: ")
        result.append(str(self.asr_client_id))
        result.append("\n  Timestamp: ")
        result.append(str(self.asr_timestamp))
        return "".join(result)

    @classmethod
    def from_xml(cls, xml_node):
        return None

    @classmethod
    def can_handle(cls, xml_node):
        return False
