<?xml version="1.0" encoding="UTF-8"?>

<!--
 CDDL HEADER START

 The contents of this file are subject to the terms of the
 Common Development and Distribution License (the "License").
 You may not use this file except in compliance with the License.

 You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
 or http://www.opensolaris.org/os/licensing.
 See the License for the specific language governing permissions
 and limitations under the License.

 When distributing Covered Code, include this CDDL HEADER in each
 file and include the License file at usr/src/OPENSOLARIS.LICENSE.
 If applicable, add the following below this CDDL HEADER, with the
 fields enclosed by brackets "[]" replaced with your own identifying
 information: Portions Copyright [yyyy] [name of copyright owner]

 CDDL HEADER END

 Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
-->

<!-- Extract the Software nodes we constructed from the varies -->
<!-- checkpoints into a XML file to be stored in the image. -->
<!-- The software node names we specified here must match the ones -->
<!-- used during the image construction process -->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
    <xsl:output method="xml" indent="yes" encoding="UTF-8" doctype-system="file:///usr/share/install/media-transfer.dtd"/>

    <xsl:template match="/">
        <media_transfer>
            <xsl:copy-of select="//software[@name='transfer-root']"/>
            <xsl:copy-of select="//software[@name='transfer-misc']"/>
            <xsl:copy-of select="//software[@name='transfer-media']"/>
        </media_transfer>
    </xsl:template>
</xsl:stylesheet>
