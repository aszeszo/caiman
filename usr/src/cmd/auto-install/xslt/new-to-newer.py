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

import sys
import os
import getopt
from subprocess import Popen, PIPE


XSLT_PROC = "/usr/bin/xsltproc"
XSLT_FILE = "new-to-newer.xslt"


def usage(exitcode=1):
    '''
        Print help page and exit script.

        Default exit code is 1, which indicates an error.  To exit
        normally, set keyword param exitcode to 0.
    '''
    this_script = os.path.basename(sys.argv[0])

    print ""
    print "%s - Convert old-style XML AI Manifests to the new schema." % \
        this_script
    print ""
    print "For convenience, the command-line interface has similar semantics "\
        "to cp(1)."
    print ""
    print "Usage:"
    print "\t%s [options] infile outfile" % this_script
    print "\t%s [options] infile... outdir" % this_script
    print "\t%s -r [options] indir... outdir" % this_script
    print "\nOptions:"
    print "\t-f        : force overwrite if output already exists"
    print "\t-r        : recursively transform .xml files in named "\
        "sub-directory"
    print "\t-h --help : print this help page and exit"

    sys.exit(exitcode)


def run_cmd(cmd):
    '''
        Execute the given command in a subprocess.

        On success, returns the stdout from running the command.
        On failure, raises one of:
            OSError
            ValueError
            Exception
    '''

    try:
        cmd_popen = Popen(cmd, shell=True, stdout=PIPE)
        (cmd_stdout, cmd_stderr) = cmd_popen.communicate()
    except OSError, err:
        print "ERROR running [%s] : [%s]" % \
            (cmd, str(err))
        raise
    except ValueError, err:
        print "ERROR running [%s] : [%s]" % \
            (cmd, str(err))
        raise

    if cmd_popen.returncode != 0:
        errstr = "ERROR: command [%s] returned [%d] : [%s]" % \
            (cmd, cmd_popen.returncode, str(cmd_stderr))
        print errstr
        raise Exception(errstr)

    if cmd_stderr is not None:
        print "WARNING: command [%s] produced stderr output: [%s]" % \
            (cmd, cmd_stderr)

    return cmd_stdout


def do_transform(xsltfile, infile, outfile, mkdirs=False, overwrite=False):
    '''
        Create the output directory, if appropriate, and run the xsltproc
        command to transform infile to oufile.

        On success, returns True.
        On failure, returns False.
    '''

    # Normalize the paths so we can check if they are really the same file
    # (doesn't always work, eg for paths beginning with "..")
    infile = os.path.normpath(infile)
    outfile = os.path.normpath(outfile)

    if infile == outfile:
        print "ERROR: source [%s] and target [%s] are the same" % \
            (infile, outfile)
        return False

    outdir = os.path.dirname(outfile)
    if (len(outdir)) and (not os.path.isdir(outdir)):
        if os.path.exists(outdir):
            print "ERROR: target dir [%s] is not a directory" % \
                outdir
            return False

        if not mkdirs:
            print "ERROR: target dir [%s] doesn't exist" % \
                outdir
            return False

        try:
            os.makedirs(outdir)
        except OSError, err:
            print "ERROR: failed to make dir [%s] : [%s]" % \
                (outdir, str(err))
            return False

    if (os.path.exists(outfile)) and (not overwrite):
        print "ERROR: target file [%s] already exists. Use -f." % \
            outfile
        return False

    # Construct command
    cmd = "%s -o %s %s %s" % (XSLT_PROC, outfile, xsltfile, infile)

    try:
        output = run_cmd(cmd)
    except:
        return False

    return True


def do_main():
    '''
        Process command line options and call do_transform() for
        each file to be processed.

        Returns: nothing.
    '''

    sources = []
    target = None
    force_overwrite = False
    recursive = False
    target_exists = False

    # Check xsltproc is installed
    if not os.access(XSLT_PROC, os.X_OK):
        print "ERROR: Cannot find %s" % XSLT_PROC
        print "You may be able to install it with:"
        print "\tpfexec pkg install pkg:/library/libxslt"
        sys.exit(1)

    # Check xsl transform file is available in same dir this
    # script was run from
    xsltdir = os.path.dirname(sys.argv[0])
    xsltfile = "%s/%s" % (xsltdir, XSLT_FILE)
    if (not os.path.exists(xsltfile)):
        print "XSLT file [%s] is missing from directory [%s]" % \
            (XSLT_FILE, xsltdir)
        sys.exit(1)

    # Fetch and process command line params and options
    try:
        optlist, args = getopt.getopt(sys.argv[1:], "frh", ["help"])
    except getopt.GetoptError:
        usage()

    for opt, arg in optlist:
        if (opt == "-f"):
            force_overwrite = True
        if (opt == "-r"):
            recursive = True
        if (opt == "-h") or (opt == "--help"):
            usage(exitcode=0)

    # There must be at least 2 params.  The last param is the
    # target; all the other params are the source(s).
    if len(args) < 2:
        usage()

    sources = args[:len(args) - 1]
    target = args[len(args) - 1]

    # note whether the target existed before we started
    if os.path.exists(target):
        target_exists = True

    # Check for invalid paramaters (pt. 1)
    if ((len(sources) > 1) and
        (not os.path.isdir(target))):
        # if there are multiple sources (files or dirs), then
        # target must be an existing directory
        print "ERROR: [%s] is not a directory" % \
            target
        sys.exit(1)

    for source in sources:
        # normalize source path
        source = os.path.normpath(source)

        # Check for invalid paramaters (pt. 2)
        if source == "/":
            print "ERROR: '/' not allowed"
            sys.exit(1)
        if not os.path.exists(source):
            print "ERROR: no such file or directory: [%s]" % \
                source
            sys.exit(1)
        if (os.path.isdir(source)) and (not recursive):
            print "ERROR: [%s] is a directory, but '-r' not specified" % \
                source
            sys.exit(1)
        if (not os.path.isdir(source)) and (recursive):
            print "ERROR: [%s] is not a directory, but '-r' was specified" % \
                source
            sys.exit(1)
        if ((os.path.isdir(source)) and
            (os.path.exists(target)) and
            (not os.path.isdir(target))):
            print "ERROR: [%s] is not a directory" % \
                target
            sys.exit(1)

        if os.path.isdir(source):
            # recursively iterate through source dir, processing each file
            for dirpath, dirnames, filenames in os.walk(source):
                # alter dirnames in-place to skip .*
                dirnames[:] = [d for d in dirnames if not d.startswith('.')]

                for name in filenames:
                    srcfile = os.path.join(dirpath, name)

                    partial_dstfile = os.path.join(dirpath, name)

                    # replicate how cp -r treats sub-dirs:
                    # 1. if source contains multiple sub-dirs, eg "a/b/c"
                    # then only create rightmost one, eg "c", under target
                    index = source.rfind("/", 1)
                    if index != -1:
                        # ensure partial_dstfile begins with source
                        if partial_dstfile.find(source) == 0:
                            partial_dstfile = partial_dstfile[index + 1:]

                    # replicate how cp -r treats sub-dirs:
                    # 2. if target already existed then chop off leftmost
                    # dir of source from target
                    if not target_exists:
                        index = partial_dstfile.find("/", 1)
                        if index != -1:
                            partial_dstfile = partial_dstfile[index + 1:]

                    dstfile = os.path.join(target, partial_dstfile)

                    if not do_transform(xsltfile, srcfile, dstfile,
                        mkdirs=True, overwrite=force_overwrite):
                        print "ERROR: Transform failed."
                        sys.exit(1)
        elif os.path.isdir(target):
            dstfile = os.path.join(target, os.path.basename(source))

            if not do_transform(xsltfile, source, dstfile,
                mkdirs=False, overwrite=force_overwrite):
                print "ERROR: Transform failed."
                sys.exit(1)
        else:
            # this must be a simple "single infile" -> "single outfile" job
            if not do_transform(xsltfile, source, target,
                mkdirs=False, overwrite=force_overwrite):
                print "ERROR: Transform failed."
                sys.exit(1)


if __name__ == "__main__":
    do_main()

    sys.exit(0)
