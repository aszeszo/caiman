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


<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
    <xsl:output method="xml" indent="yes" encoding="UTF-8" 
     doctype-system="file:///usr/share/install/ai.dtd"/>
    

    <xsl:template match="/">
        <xsl:if test="auto_install">
            <auto_install>
                <xsl:apply-templates select="auto_install/ai_instance"/>
            </auto_install>
        </xsl:if>    
    </xsl:template>

    <xsl:template match="auto_install/ai_instance">
        <xsl:copy>
            <xsl:if test="@name">
                <xsl:attribute name="name">
                    <xsl:value-of select="@name"/>
                </xsl:attribute>
            </xsl:if>    
            <xsl:if test="@auto_reboot">
                <xsl:attribute name="auto_reboot">
                    <xsl:value-of select="@auto_reboot"/>
                </xsl:attribute>
            </xsl:if>    
            <xsl:if test="@http_proxy">
                <xsl:attribute name="http_proxy">
                    <xsl:value-of select="@http_proxy"/>
                </xsl:attribute>
            </xsl:if>    
            <xsl:if test="target">
                <target>
                    <xsl:for-each select="target/target_device">
                        <xsl:apply-templates select="disk"/>
                    </xsl:for-each>
                    <logical>
                        <xsl:choose>
                          <xsl:when
                           test="target/target_device/swap/zvol/size/@val = '0mb'">
                            <xsl:attribute name="noswap">
                                <xsl:text>true</xsl:text>
                            </xsl:attribute>
                          </xsl:when>
                          <xsl:otherwise>
                            <xsl:attribute name="noswap">
                                <xsl:text>false</xsl:text>
                            </xsl:attribute>
                          </xsl:otherwise>
                        </xsl:choose>    
                        <xsl:choose>
                          <xsl:when
                           test="target/target_device/dump/zvol/size/@val = '0mb'">
                            <xsl:attribute name="nodump">
                                <xsl:text>true</xsl:text>
                            </xsl:attribute>
                          </xsl:when>
                          <xsl:otherwise>
                            <xsl:attribute name="nodump">
                                <xsl:text>false</xsl:text>
                            </xsl:attribute>
                          </xsl:otherwise>
                        </xsl:choose>    
                        <zpool name="rpool" is_root="true">
                            <vdev name="vdev" redundancy="none"/>
                            <xsl:for-each select="target/target_device">
                                <xsl:apply-templates select="swap"/>
                                <xsl:apply-templates select="dump"/>
                            </xsl:for-each>
                        </zpool>
                    </logical>
                </target>
            </xsl:if>
            <xsl:apply-templates select="software"/>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="disk">
        <xsl:copy>
            <xsl:choose>
                <xsl:when test="partition or slice"/>
                <xsl:otherwise>
                    <xsl:attribute name="whole_disk">
                        <xsl:text>true</xsl:text>
                    </xsl:attribute>
                    <xsl:attribute name="in_zpool">
                        <xsl:text>rpool</xsl:text>
                    </xsl:attribute>
                    <xsl:attribute name="in_vdev">
                        <xsl:text>vdev</xsl:text>
                    </xsl:attribute>
                </xsl:otherwise>
            </xsl:choose>        
            <xsl:apply-templates select="disk_name|disk_prop|disk_keyword|iscsi"/>
            <xsl:if test="partition or slice">
                <xsl:choose>
                    <xsl:when test="partition">
                        <xsl:apply-templates select="partition"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:apply-templates select="slice"/>
                    </xsl:otherwise>
                </xsl:choose>        
            </xsl:if>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="disk_name|disk_keyword|iscsi">
        <xsl:copy-of select="."/>
    </xsl:template>

    <xsl:template match="disk_prop">
        <disk_prop>
        <xsl:if test="@dev_type">
            <xsl:attribute name="dev_type">
                <xsl:value-of select="@dev_type"/>
            </xsl:attribute>
        </xsl:if>
        <xsl:if test="@dev_vendor">
            <xsl:attribute name="dev_vendor">
                <xsl:value-of select="@dev_vendor"/>
            </xsl:attribute>
        </xsl:if>
        <xsl:if test="@dev_size">
            <xsl:attribute name="dev_size">
                <xsl:choose>
                    <xsl:when test="number(@dev_size) > 0">
                        <xsl:value-of select="concat(@dev_size, 'mb')"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="@dev_size"/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:attribute>
        </xsl:if>
        </disk_prop>
    </xsl:template>

    <xsl:template match="size">
        <size>
        <xsl:if test="@start_sector">
            <xsl:attribute name="start_sector">
                <xsl:value-of select="@start_sector"/>
            </xsl:attribute>
        </xsl:if>
        <xsl:if test="@val">
            <xsl:attribute name="val">
                <xsl:choose>
                    <!-- Uppercase -->
                    <xsl:when test="contains(@val, 'GIGABYTE')">
                        <xsl:value-of select="concat(substring-before(@val, 'GIGABYTE'), 'gb')"/>
                    </xsl:when>
                    <xsl:when test="contains(@val, 'GIGABYTES')">
                        <xsl:value-of select="concat(substring-before(@val, 'GIGABYTES'), 'gb')"/>
                    </xsl:when>
                    <xsl:when test="contains(@val, 'MEGABYTE')">
                        <xsl:value-of select="concat(substring-before(@val, 'MEGABYTE'), 'mb')"/>
                    </xsl:when>
                    <xsl:when test="contains(@val, 'MEGABYTES')">
                        <xsl:value-of select="concat(substring-before(@val, 'MEGABYTES'), 'mb')"/>
                    </xsl:when>
                    <xsl:when test="contains(@val, 'SEC')">
                        <xsl:value-of select="concat(substring-before(@val, 'SEC'), 'secs')"/>
                    </xsl:when>
                    <xsl:when test="contains(@val, 'SECTORS')">
                        <xsl:value-of select="concat(substring-before(@val, 'SECTORS'), 'secs')"/>
                    </xsl:when>
                    <!-- Lowercase -->
                    <xsl:when test="contains(@val, 'gigabyte')">
                        <xsl:value-of select="concat(substring-before(@val, 'gigabyte'), 'gb')"/>
                    </xsl:when>
                    <xsl:when test="contains(@val, 'gigabytes')">
                        <xsl:value-of select="concat(substring-before(@val, 'gigabytes'), 'gb')"/>
                    </xsl:when>
                    <xsl:when test="contains(@val, 'megabyte')">
                        <xsl:value-of select="concat(substring-before(@val, 'megabyte'), 'mb')"/>
                    </xsl:when>
                    <xsl:when test="contains(@val, 'megabytes')">
                        <xsl:value-of select="concat(substring-before(@val, 'megabytes'), 'mb')"/>
                    </xsl:when>
                    <xsl:when test="contains(@val, 'sec')">
                        <xsl:value-of select="concat(substring-before(@val, 'sec'), 'secs')"/>
                    </xsl:when>
                    <xsl:when test="contains(@val, 'sectors')">
                        <xsl:value-of select="concat(substring-before(@val, 'sectors'), 'secs')"/>
                    </xsl:when>
                    <xsl:when test="number(@val) > 0">
                        <xsl:value-of select="concat(@val, 'mb')"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="@val"/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:attribute>
        </xsl:if>
        </size>
    </xsl:template>

    <xsl:template match="partition">
        <xsl:copy>
            <xsl:if test="@name">
                <xsl:attribute name="name">
                    <xsl:value-of select="@name"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="@action">
                <xsl:attribute name="action">
                    <xsl:choose>
                        <xsl:when test="@action='use_existing'">
                            <xsl:text>use_existing_solaris2</xsl:text>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:value-of select="@action"/>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="@part_type">
                <xsl:attribute name="part_type">
                    <xsl:value-of select="@part_type"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:apply-templates select="size"/>
            <xsl:if test="@part_type = '191' or @part_type = '130' or @action='use_existing'">
                <xsl:if test="../slice">
                    <xsl:apply-templates select="../slice"/>
                </xsl:if>
            </xsl:if>
       </xsl:copy>
    </xsl:template>

    <xsl:template match="slice">
        <xsl:copy>
            <xsl:attribute name="name">
                <xsl:value-of select="@name"/>
            </xsl:attribute>
            <xsl:if test="@action">
                <xsl:attribute name="action">
                    <xsl:value-of select="@action"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="@is_swap">
                <xsl:attribute name="is_swap">
                    <xsl:value-of select="@is_swap"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="@is_root = 'true' or count(../slice) = 1">
                <xsl:attribute name="in_zpool">
                    <xsl:text>rpool</xsl:text>
                </xsl:attribute>
                <xsl:attribute name="in_vdev">
                    <xsl:text>vdev</xsl:text>
                </xsl:attribute>
            </xsl:if>
            <xsl:apply-templates select="size"/>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="swap">
        <xsl:if test="zvol/size/@val != '0mb'">
            <xsl:choose>
                <xsl:when test="starts-with(zvol/@name, 'rpool')">
                    <xsl:variable name="swap_name" 
                     select="substring-after(zvol/@name, '/')"/>
                    <zvol name="{$swap_name}" action="create" 
                     use="swap">
                        <xsl:apply-templates select=".//size"/>
                    </zvol>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:variable name="swap_name" 
                     select="zvol/@name"/>
                    <zvol name="{$swap_name}" action="create" 
                     use="swap">
                        <xsl:apply-templates select=".//size"/>
                    </zvol>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:if>
    </xsl:template>

    <xsl:template match="dump">
        <xsl:if test="zvol/size/@val != '0mb'">
            <xsl:choose>
                <xsl:when test="starts-with(zvol/@name, 'rpool')">
                    <xsl:variable name="dump_name" 
                     select="substring-after(zvol/@name, '/')"/>
                    <zvol name="{$dump_name}" action="create" 
                     use="dump">
                        <xsl:apply-templates select=".//size"/>
                    </zvol>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:variable name="dump_name" 
                     select="zvol/@name"/>
                    <zvol name="{$dump_name}" action="create" 
                     use="dump">
                        <xsl:apply-templates select=".//size"/>
                    </zvol>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:if>
    </xsl:template>

    <xsl:template name="generate-software-node">
        <xsl:param name="trans_type"/>
        <software type="{$trans_type}">
            <xsl:copy-of select="source"/>
            <xsl:for-each select="software_data">
                <software_data action="{@action}">
                    <xsl:copy-of select="name"/>
                </software_data>
            </xsl:for-each>
        </software>
    </xsl:template>

    <xsl:template match="software">
            <xsl:choose>
                <xsl:when test="software_data/@type">
                    <xsl:choose>
                        <xsl:when test="software_data/@type = 'ips'">
                            <xsl:variable name="trans_type">IPS</xsl:variable>
                            <xsl:call-template name="generate-software-node">
                                <xsl:with-param name="trans_type" select="$trans_type"/>
                            </xsl:call-template>
                        </xsl:when>
                        <xsl:when test="software_data/@type = 'svr4'">
                            <xsl:variable name="trans_type">SVR4</xsl:variable>
                            <xsl:call-template name="generate-software-node">
                                <xsl:with-param name="trans_type" select="$trans_type"/>
                            </xsl:call-template>
                        </xsl:when>
                        <xsl:when test="software_data/@type = 'cpio'">
                            <xsl:variable name="trans_type">ARCHIVE</xsl:variable>
                            <xsl:call-template name="generate-software-node">
                                <xsl:with-param name="trans_type" select="$trans_type"/>
                            </xsl:call-template>
                        </xsl:when>
                        <xsl:when test="software_data/@type = 'archive'">
                            <xsl:variable name="trans_type">CPIO</xsl:variable>
                            <xsl:call-template name="generate-software-node">
                                <xsl:with-param name="trans_type" select="$trans_type"/>
                            </xsl:call-template>
                        </xsl:when>
                        <xsl:when test="software_data/@type = 'image'">
                            <xsl:variable name="trans_type">IMAGE</xsl:variable>
                            <xsl:call-template name="generate-software-node">
                                <xsl:with-param name="trans_type" select="$trans_type"/>
                            </xsl:call-template>
                        </xsl:when>
                        <xsl:when test="software_data/@type = 'p5i'">
                            <xsl:variable name="trans_type">P5I</xsl:variable>
                            <xsl:call-template name="generate-software-node">
                                <xsl:with-param name="trans_type" select="$trans_type"/>
                            </xsl:call-template>
                        </xsl:when>
                        <xsl:when test="software_data/@type = 'du'">
                            <xsl:variable name="trans_type">DU</xsl:variable>
                            <xsl:call-template name="generate-software-node">
                                <xsl:with-param name="trans_type" select="$trans_type"/>
                            </xsl:call-template>
                        </xsl:when>
                        <xsl:when test="software_data/@type = 'p5p'">
                            <xsl:variable name="trans_type">P5P</xsl:variable>
                            <xsl:call-template name="generate-software-node">
                                <xsl:with-param name="trans_type" select="$trans_type"/>
                            </xsl:call-template>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:variable name="trans_type" 
                             select="software_data/@type"/>
                            <xsl:call-template name="generate-software-node">
                                <xsl:with-param name="trans_type" select="$trans_type"/>
                            </xsl:call-template>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:copy-of select="source"/>
                    <xsl:copy-of select="software_data"/>
                </xsl:otherwise>
            </xsl:choose>
    </xsl:template>
</xsl:stylesheet>

