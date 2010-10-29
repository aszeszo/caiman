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

 Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
    <xsl:output method="xml" indent="yes" encoding="UTF-8" doctype-system="file:///tmp/manifest.dtd"/>

    <!-- Restructure the contents of the DataObjectCache to -->
    <!-- resemble a DC Manifest. -->
    <!-- For now, we are only doing a high-level restructuring. -->
    <!-- That is, we create the top-level <dc> element, the -->
    <!-- second-level <distro> element (with any relevant attributes -->
    <!-- from the DOC) and the 5 sub-elements of <distro>: -->
    <!-- <distro_spec>, <target>, <software>, <execution> and -->
    <!-- <configuration>, copied unmodified and in their -->
    <!-- entirety from the DOC, as many times as they occur. -->

    <xsl:template match="/">
        <dc>
            <distro>
                <xsl:choose>
                    <xsl:when test="//distro">
                        <!-- Copy all <distro>'s attributes. -->
                        <xsl:copy-of select="//distro/@*"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <!-- If there was no <distro> in source document, -->
                        <!-- then provide the compulsory name attribute. -->
                        <xsl:attribute name="name">
                            <xsl:text>generated manifest</xsl:text>
                        </xsl:attribute>
                    </xsl:otherwise>
                </xsl:choose>

                <!-- Place these other elements (and their sub-elements) -->
                <!-- directly under distro, regardless of where they -->
                <!-- were found in the source document. If they are not -->
                <!-- found, they will just be skipped.  -->
                <xsl:copy-of select="//distro_spec"/>
                <xsl:copy-of select="//target"/>
                <xsl:copy-of select="//software"/>
                <xsl:copy-of select="//execution"/>
                <xsl:copy-of select="//configuration"/>
            </distro>
        </dc>
    </xsl:template>
</xsl:stylesheet>
