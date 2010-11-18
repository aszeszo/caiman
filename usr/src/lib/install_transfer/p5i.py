#
##
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

'''Transfer P5I checkpoint. Sub-class of the checkpoint class'''

import pkg.client.api_errors as api_errors
import pkg.p5i as p5i

from solaris_install.transfer.info import Origin
from solaris_install.transfer.info import Publisher
from solaris_install.transfer.info import Source
from solaris_install.transfer.info import ACTION, CONTENTS, \
PURGE_HISTORY, APP_CALLBACK, INSTALL
from solaris_install.transfer.ips import TransferIPS
from solaris_install.transfer.ips import TransferIPSAttr


class TransferP5I(TransferIPS):
    '''Subclass of the TransferIPS checkpoint to be used for IPS transfers
       using a p5i file. The input comes from the DOC.
    '''
    def __init__(self, name):
        super(TransferP5I, self).__init__(name)
        self._p5i_lst = []
        self.img_action = "use_existing"

    def _parse_src(self, soft_node):
        src_list = soft_node.get_children(Source.SOURCE_LABEL, Source)

        src = src_list[0]
        pub_list = src.get_children(Publisher.PUBLISHER_LABEL, Publisher)

        pub = pub_list.pop(0)
        orig_list = pub.get_children(Origin.ORIGIN_LABEL, Origin)

        p5i_file = orig_list[0].origin

        try:
            self._p5i_lst = p5i.parse(location=p5i_file)
        except api_errors.InvalidP5IFile:
            raise Exception(p5i_file +
                            " does not have the correct format")

        # If there are any further publishers specified, treat those
        # as publishers for the ips image
        if len(pub_list) > 0:
            pub = pub_list.pop(0)
            self._set_publisher_info(pub, preferred=True)
            for pub in pub_list:
                self._set_publisher_info(pub, preferred=False)

    def _parse_transfer_node(self, soft_node):
        trans_attr = dict()
        for p5i_file in self._p5i_lst:
            pub, pkglst = p5i_file
            trans_attr[ACTION] = INSTALL
            trans_attr[CONTENTS] = pkglst
            trans_attr[APP_CALLBACK] = None
            trans_attr[PURGE_HISTORY] = None

        # Append the information found to the list of
        # transfers that will be performed
        if trans_attr not in self._transfer_list:
            self._transfer_list.append(trans_attr)


class TransferP5IAttr(TransferIPSAttr):
    '''Subclass of the TransferIPS checkpoint to be used for IPS transfers
       using a p5i file where the attributes are written directly for the
       input.
    '''
    def __init__(self, name):
        super(TransferP5IAttr, self).__init__(name)
        self._p5i_lst = []
        self.action = "use_existing"

    def _parse_input(self):

        self.logger.info("Reading the p5i file")
        if self.src is None:
            raise Exception("A p5i file must be specified")

        p5i_file = self.src
        self.logger.debug("p5i file specified is " + p5i_file)
        self._p5i_lst = p5i.parse(location=p5i_file)
        trans_attr = dict()
        for p5i_file in self._p5i_lst:
            pub, pkglst = p5i_file
            trans_attr[ACTION] = INSTALL
            trans_attr[CONTENTS] = pkglst
            trans_attr[APP_CALLBACK] = None
            trans_attr[PURGE_HISTORY] = None

        # Append the information found to the list of
        # transfers that will be performed
        if trans_attr not in self._transfer_list:
            self._transfer_list.append(trans_attr)
