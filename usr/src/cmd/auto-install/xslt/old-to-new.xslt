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
    <xsl:output method="xml" indent="yes" encoding="UTF-8" doctype-system="file:///usr/share/auto_install/ai.dtd"/>

    <xsl:template match="/">
        <!-- We need to process both criteria manifests (with embedded AI -->
        <!-- and/or SC manifests) and simple AI manifests. That is, both: -->
        <!--     <ai_criteria_manifest> -->
        <!--         <ai_embedded_manifest> -->
        <!--             <ai_manifest> -->
        <!--                 ... -->
        <!--             </ai_manifest> -->
        <!--         </ai_embedded_manifest> -->
        <!--         <sc_embedded_manifest> -->
        <!--             ... -->
        <!--         </sc_embedded_manifest> -->
        <!--     </ai_criteria_manifest> -->
        <!-- and: -->
        <!--     <ai_manifest> -->
        <!--         ... -->
        <!--     </ai_manifest> -->

        <xsl:if test="ai_criteria_manifest or ai_manifest">
            <auto_install>
                <xsl:apply-templates select="ai_criteria_manifest"/>
                <xsl:apply-templates select="ai_manifest"/>
            </auto_install>
        </xsl:if>
    </xsl:template>

    <xsl:template match="ai_criteria_manifest">
        <xsl:apply-templates select="ai_embedded_manifest"/>
        <xsl:apply-templates select="sc_embedded_manifest"/>
    </xsl:template>

    <xsl:template match="ai_embedded_manifest">
        <xsl:apply-templates select="ai_manifest"/>
    </xsl:template>


    <xsl:template match="ai_manifest">
        <ai_instance name="{@name}">
            <xsl:if test="ai_auto_reboot">
                <xsl:attribute name="auto_reboot">
                    <xsl:value-of select="normalize-space(ai_auto_reboot)"/>
                </xsl:attribute>
            </xsl:if>

            <xsl:if test="ai_http_proxy/@url">
                <xsl:attribute name="http_proxy">
                    <xsl:value-of select="normalize-space(ai_http_proxy/@url)"/>
                </xsl:attribute>
            </xsl:if>

            <xsl:call-template name="target_swap_dump_partitioning_slices"/>

            <xsl:call-template name="install_uninstall_repo"/>

            <xsl:apply-templates select="ai_add_drivers"/>

            <!-- Handle sc_embedded_manifest, where ai_manifest is also present -->
            <xsl:if test="../../sc_embedded_manifest">
                <xsl:copy-of select="../../sc_embedded_manifest"/>
            </xsl:if>
        </ai_instance>
    </xsl:template>


    <!-- Handle following elements from -->
    <!-- the old schema which all transform to parts of the -->
    <!-- target tree in the new schema: -->
    <!-- ai_target_device, ai_swap_device, ai_dump_device, -->
    <!-- ai_device_partitioning, ai_device_vtoc_slices. -->

    <xsl:template name="target_swap_dump_partitioning_slices">
        <xsl:if test="ai_target_device or ai_swap_device or ai_dump_device or ai_device_partitioning or ai_device_vtoc_slices">
            <target>
                <xsl:if test="ai_target_device or ai_device_partitioning">
                    <target_device>
                        <xsl:call-template name="target_partitioning_slices"/>
                    </target_device>
                </xsl:if>

                <xsl:apply-templates select="ai_swap_device"/>
                <xsl:apply-templates select="ai_dump_device"/>
            </target>
        </xsl:if>
    </xsl:template>


    <!-- Handle: -->
    <!-- ai_target_device, -->
    <!-- ai_device_partitioning -->
    <!-- ai_device_vtoc_slices -->
    <!-- elements -->

    <xsl:template name="target_partitioning_slices">
        <xsl:if test="ai_target_device or ai_device_partitioning or ai_device_vtoc_slices">
            <disk>
                <xsl:apply-templates select="ai_target_device/target_device_name"/>
                <xsl:apply-templates select="ai_target_device/target_device_select_volume_name"/>
                <xsl:apply-templates select="ai_target_device/target_device_select_id"/>
                <xsl:apply-templates select="ai_target_device/target_device_select_device_path"/>

                <!-- The following elements are handled together: -->
                <!-- target_device_type, target_device_size, -->
                <!-- target_device_vendor -->
                <xsl:call-template name="target_device_type_size_vendor"/>

                <xsl:apply-templates select="ai_target_device/target_device_use_solaris_partition"/>

                <!-- All the target_device_iscsi_* elements -->
                <!-- are handled together. -->
                <xsl:call-template name="target_device_iscsi"/>

                <xsl:apply-templates select="ai_device_partitioning"/>
                <xsl:apply-templates select="ai_device_vtoc_slices"/>
            </disk>
        </xsl:if>
    </xsl:template>


    <xsl:template match="ai_target_device/target_device_name">
        <xsl:choose>
            <xsl:when test="normalize-space(text()) = 'boot_disk'">
                <disk_keyword>
                    <xsl:attribute name="key">
                        <xsl:value-of select="normalize-space(text())"/>
                    </xsl:attribute>
                </disk_keyword>
            </xsl:when>
            <xsl:otherwise>
                <disk_name name_type='ctd'>
                    <xsl:attribute name="name">
                        <xsl:value-of select="normalize-space(text())"/>
                    </xsl:attribute>
                </disk_name>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template match="ai_target_device/target_device_select_volume_name">
        <disk_name name_type='volid'>
            <xsl:attribute name="name">
                <xsl:value-of select="normalize-space(text())"/>
            </xsl:attribute>
        </disk_name>
    </xsl:template>

    <xsl:template match="ai_target_device/target_device_select_id">
        <disk_name name_type='devid'>
            <xsl:attribute name="name">
                <xsl:value-of select="normalize-space(text())"/>
            </xsl:attribute>
        </disk_name>
    </xsl:template>

    <xsl:template match="ai_target_device/target_device_select_device_path">
        <disk_name name_type='devpath'>
            <xsl:attribute name="name">
                <xsl:value-of select="normalize-space(text())"/>
            </xsl:attribute>
        </disk_name>
    </xsl:template>


    <!-- More than one of the following elements can be specified: -->
    <!-- target_device_type, target_device_size, target_device_vendor -->
    <!-- and each one corresponds to an attribute on a single -->
    <!-- disk_prop element in the new schema. -->

    <xsl:template name="target_device_type_size_vendor">
        <xsl:if test="ai_target_device/target_device_type or ai_target_device/target_device_size or ai_target_device/target_device_vendor">
            <disk_prop>
                <xsl:if test="ai_target_device/target_device_type">
                    <xsl:attribute name="dev_type">
                        <xsl:value-of select="normalize-space(ai_target_device/target_device_type)"/>
                    </xsl:attribute>
                </xsl:if>
                <xsl:if test="ai_target_device/target_device_size">
                    <xsl:attribute name="dev_size">
                        <xsl:value-of select="normalize-space(ai_target_device/target_device_size)"/>
                        <!-- Old values were assumed to be in 'sectors'.  -->
                        <xsl:text>Sec</xsl:text>
                    </xsl:attribute>
                </xsl:if>
                <xsl:if test="ai_target_device/target_device_vendor">
                    <xsl:attribute name="dev_vendor">
                        <xsl:value-of select="normalize-space(ai_target_device/target_device_vendor)"/>
                    </xsl:attribute>
                </xsl:if>
            </disk_prop>
        </xsl:if>
    </xsl:template>

    <!-- FIXME: does this need to be combined with ai_device_partitioning? -->
    <xsl:template match="ai_target_device/target_device_use_solaris_partition">
        <xsl:variable name="use_partition_val"
            select="translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')"/>
        <xsl:if test="normalize-space($use_partition_val) = true">
            <partition action='use_existing'/>
        </xsl:if>
    </xsl:template>

    <!-- The following are separate elements in old but -->
    <!-- correspond to attributes or sub-elements of a -->
    <!-- single iscsi element in new: -->
    <!-- target_device_iscsi_target_name, target_device_iscsi_target_ip, -->
    <!-- target_device_iscsi_target_lun, target_device_iscsi_target_port, -->
    <!-- target_device_iscsi_parameter_source. -->

    <xsl:template name="target_device_iscsi">
        <xsl:if test="ai_target_device/target_device_iscsi_target_name or ai_target_device/target_device_iscsi_target_ip or ai_target_device/target_device_iscsi_target_lun or ai_target_device/target_device_iscsi_target_port or ai_target_device/target_device_iscsi_parameter_source">
            <iscsi>
                <xsl:if test="ai_target_device/target_device_iscsi_target_name">
                    <xsl:attribute name="name">
                        <xsl:value-of select="normalize-space(ai_target_device/target_device_iscsi_target_name)"/>
                    </xsl:attribute>
                </xsl:if>
                <xsl:if test="ai_target_device/target_device_iscsi_target_lun">
                    <xsl:attribute name="target_lun">
                        <xsl:value-of select="normalize-space(ai_target_device/target_device_iscsi_target_lun)"/>
                    </xsl:attribute>
                </xsl:if>
                <xsl:if test="ai_target_device/target_device_iscsi_target_port">
                    <xsl:attribute name="target_port">
                        <xsl:value-of select="normalize-space(ai_target_device/target_device_iscsi_target_port)"/>
                    </xsl:attribute>
                </xsl:if>
                <xsl:if test="ai_target_device/target_device_iscsi_parameter_source">
                    <xsl:attribute name="source">
                        <xsl:value-of select="normalize-space(ai_target_device/target_device_iscsi_parameter_source)"/>
                    </xsl:attribute>
                </xsl:if>
                <!-- 'ip' must be processed last as it transforms to a -->
                <!-- sub-element and attributes must be completed before -->
                <!-- sub-elements can be added. -->
                <xsl:if test="ai_target_device/target_device_iscsi_target_ip">
                    <ip>
                        <xsl:value-of select="normalize-space(ai_target_device/target_device_iscsi_target_ip)"/>
                    </ip>
                </xsl:if>
            </iscsi>
        </xsl:if>
    </xsl:template>


    <!-- Handle ai_swap_device -->

    <xsl:template match="ai_swap_device">
        <target_device>
            <swap>
                <zvol action="create" name="swap">
                    <xsl:apply-templates select="ai_swap_size"/>
                </zvol>
            </swap>
        </target_device>
    </xsl:template>

    <xsl:template match="ai_swap_size">
        <size>
            <xsl:attribute name="val">
                <xsl:value-of select="normalize-space(text())"/>
                <!-- Old values were assumed to be in mb.  -->
                <xsl:text>mb</xsl:text>
            </xsl:attribute>
        </size>
    </xsl:template>


    <!-- Handle ai_dump_device -->

    <xsl:template match="ai_dump_device">
        <target_device>
            <dump>
                <zvol action="create" name="dump">
                    <xsl:apply-templates select="ai_dump_size"/>
                </zvol>
            </dump>
        </target_device>
    </xsl:template>

    <xsl:template match="ai_dump_size">
        <size>
            <xsl:attribute name="val">
                <xsl:value-of select="normalize-space(text())"/>
                <!-- Old values were assumed to be in mb.  -->
                <xsl:text>mb</xsl:text>
            </xsl:attribute>
        </size>
    </xsl:template>


    <!-- handle ai_device_partitioning -->

    <xsl:template match="ai_device_partitioning">
        <partition>
            <xsl:if test="partition_action">
                <xsl:attribute name="action">
                    <xsl:value-of select="normalize-space(partition_action)"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="partition_number">
                <xsl:attribute name="name">
                    <xsl:value-of select="normalize-space(partition_number)"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="partition_type">
                <xsl:attribute name="part_type">
                    <xsl:value-of select="normalize-space(partition_type)"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="partition_size">
                <size>
                    <xsl:attribute name="val">
                        <xsl:variable name="size_val"
                            select="translate(partition_size, 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')"/>
                        <xsl:choose>
                            <xsl:when test="normalize-space($size_val) = 'MAX_SIZE'">
                                <xsl:text>0</xsl:text>
                            </xsl:when>
                            <xsl:otherwise>
                                <xsl:value-of select="normalize-space($size_val)"/>
                            </xsl:otherwise>
                        </xsl:choose>

                        <xsl:choose>
                            <xsl:when test="partition_size_units">
                                <xsl:value-of select="normalize-space(partition_size_units)"/>
                            </xsl:when>
                            <xsl:otherwise>
                                <!-- If no size units given, default to mb.  -->
                                <xsl:text>mb</xsl:text>
                            </xsl:otherwise>
                        </xsl:choose>
                    </xsl:attribute>

                    <!-- This is for when partition_start_sector is -->
                    <!-- specified along with partition_size. -->
                    <xsl:if test="partition_start_sector">
                        <xsl:attribute name="start_sector">
                            <xsl:value-of select="normalize-space(partition_start_sector)"/>
                        </xsl:attribute>
                    </xsl:if>
                </size>
            </xsl:if>
            <xsl:if test="not(partition_size)">
                <!-- This is for when partition_start_sector is -->
                <!-- specified WITHOUT partition_size. (Should only -->
                <!-- happen for action=delete.) -->
                <xsl:if test="partition_start_sector">
                    <size>
                        <!-- size/val is mandatory, so use 0. -->
                        <xsl:attribute name="val">
                            <xsl:text>0</xsl:text>
                        </xsl:attribute>
                        <xsl:attribute name="start_sector">
                            <xsl:value-of select="normalize-space(partition_start_sector)"/>
                        </xsl:attribute>
                    </size>
                </xsl:if>
            </xsl:if>
        </partition>
    </xsl:template>


    <!-- handle ai_device_vtoc_slices -->

    <xsl:template match="ai_device_vtoc_slices">
        <slice>
            <xsl:if test="slice_action">
                <xsl:attribute name="action">
                    <xsl:value-of select="normalize-space(slice_action)"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="slice_number">
                <xsl:attribute name="name">
                    <xsl:value-of select="normalize-space(slice_number)"/>
                </xsl:attribute>

                <!-- if manifest specified a -->
                <!-- target_device_install_slice_number value and -->
                <!-- it is the same as the current slice_number then -->
                <!-- set attribute is_root="true" on current slice. -->
                <xsl:if test="/ai_manifest/ai_target_device/target_device_install_slice_number">
                    <xsl:if test="normalize-space(/ai_manifest/ai_target_device/target_device_install_slice_number) = normalize-space(slice_number)">
                        <xsl:attribute name="is_root">
                            <xsl:text>true</xsl:text>
                        </xsl:attribute>
                    </xsl:if>
                </xsl:if>
            </xsl:if>
            <xsl:if test="slice_on_existing">
                <xsl:attribute name="force">
                    <xsl:variable name="on_existing_upr"
                        select="translate(slice_on_existing, 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')"/>
                    <xsl:choose>
                        <xsl:when test="normalize-space($on_existing_upr) = 'OVERWRITE'">
                            <xsl:text>true</xsl:text>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:text>false</xsl:text>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="slice_size">
                <size>
                    <xsl:attribute name="val">
                        <xsl:variable name="size_val"
                            select="translate(slice_size, 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')"/>
                        <xsl:choose>
                            <xsl:when test="normalize-space($size_val) = 'MAX_SIZE'">
                                <xsl:text>0</xsl:text>
                            </xsl:when>
                            <xsl:otherwise>
                                <xsl:value-of select="normalize-space($size_val)"/>
                            </xsl:otherwise>
                        </xsl:choose>

                        <xsl:choose>
                            <xsl:when test="slice_size_units">
                                <xsl:value-of select="normalize-space(slice_size_units)"/>
                            </xsl:when>
                            <xsl:otherwise>
                                <!-- If no size units given, default to mb.  -->
                                <xsl:text>mb</xsl:text>
                            </xsl:otherwise>
                        </xsl:choose>
                    </xsl:attribute>
                </size>
            </xsl:if>
        </slice>
    </xsl:template>


    <!-- Handle all the ai_*_packages  and ai_pkg_repo_* elements -->

    <xsl:template name="install_uninstall_repo">
        <xsl:if test="ai_install_packages or ai_uninstall_packages or ai_pkg_repo_default_publisher or ai_pkg_repo_default_authority or ai_pkg_repo_addl_publisher or ai_pkg_repo_addl_authority">
            <software>
                <xsl:call-template name="repos"/>

                <xsl:apply-templates select="ai_packages"/>
                <xsl:apply-templates select="ai_install_packages"/>
                <xsl:apply-templates select="ai_uninstall_packages"/>
            </software>
        </xsl:if>
    </xsl:template>


    <!-- Handle ai_*_packages -->

    <xsl:template match="ai_packages">
        <software_data>
            <xsl:attribute name="action">
                <xsl:text>install</xsl:text>
            </xsl:attribute>

            <xsl:apply-templates select="pkg"/>
        </software_data>
    </xsl:template>

    <xsl:template match="ai_install_packages">
        <software_data>
            <xsl:attribute name="action">
                <xsl:text>install</xsl:text>
            </xsl:attribute>

            <xsl:apply-templates select="pkg"/>
        </software_data>
    </xsl:template>

    <xsl:template match="ai_uninstall_packages">
        <software_data>
            <xsl:attribute name="action">
                <xsl:text>uninstall</xsl:text>
            </xsl:attribute>

            <xsl:apply-templates select="pkg"/>
        </software_data>
    </xsl:template>

    <xsl:template match="pkg">
        <xsl:if test="@name">
            <!-- If pkg name was a comma-separated list, break it up into pkg names. -->
            <xsl:call-template name="package_name_list">
                <xsl:with-param name="str" select="@name"/>
                <xsl:with-param name="splitString" select="','"/>
            </xsl:call-template>
        </xsl:if>
    </xsl:template>


    <!-- Handle all the ai_pkg_repo_* elements -->

    <xsl:template name="repos">
        <xsl:if test="ai_pkg_repo_default_publisher or ai_pkg_repo_default_authority or ai_pkg_repo_addl_publisher or ai_pkg_repo_addl_authority">
            <source>
                <xsl:apply-templates select="ai_pkg_repo_default_publisher"/>
                <xsl:apply-templates select="ai_pkg_repo_default_authority"/>
                <xsl:apply-templates select="ai_pkg_repo_addl_publisher"/>
                <xsl:apply-templates select="ai_pkg_repo_addl_authority"/>
            </source>
        </xsl:if>
    </xsl:template>

    <xsl:template match="ai_pkg_repo_default_publisher">
        <xsl:apply-templates select="main"/>
    </xsl:template>

    <xsl:template match="ai_pkg_repo_default_authority">
        <xsl:apply-templates select="main"/>
    </xsl:template>

    <xsl:template match="ai_pkg_repo_addl_publisher">
        <xsl:apply-templates select="main"/>
    </xsl:template>

    <xsl:template match="ai_pkg_repo_addl_authority">
        <xsl:apply-templates select="main"/>
    </xsl:template>

    <xsl:template match="main">
        <publisher>
            <xsl:if test="@publisher">
                <xsl:attribute name="name">
                    <xsl:value-of select="normalize-space(@publisher)"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="@authname">
                <xsl:attribute name="name">
                    <xsl:value-of select="normalize-space(@authname)"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="@url">
                <origin>
                    <xsl:attribute name="name">
                        <xsl:value-of select="normalize-space(@url)"/>
                    </xsl:attribute>
                </origin>
            </xsl:if>
            <!-- This assumes that mirror will not be present unless -->
            <!-- corresponding main is also present. -->
            <xsl:if test="../mirror/@url">
                <mirror>
                    <xsl:attribute name="name">
                        <xsl:value-of select="normalize-space(../mirror/@url)"/>
                    </xsl:attribute>
                </mirror>
            </xsl:if>
        </publisher>
    </xsl:template>


    <!-- Handle ai_add_drivers -->

    <xsl:template match="ai_add_drivers">
        <add_drivers>
            <xsl:apply-templates select="bundle"/>
            <xsl:apply-templates select="searchall"/>
        </add_drivers>
    </xsl:template>

    <xsl:template match="bundle">
        <software>
            <source>
                <xsl:if test="@location">
                    <publisher>
                        <origin>
                            <xsl:attribute name="name">
                                <xsl:value-of select="normalize-space(@location)"/>
                            </xsl:attribute>
                        </origin>
                    </publisher>
                </xsl:if>
            </source>

            <xsl:if test="@type or @noinstall or @name">
                <software_data>
                    <xsl:if test="@type">
                        <xsl:attribute name="type">
                            <xsl:value-of select="normalize-space(@type)"/>
                        </xsl:attribute>
                    </xsl:if>

                    <xsl:if test="@noinstall">
                        <xsl:variable name="noinstall_upr"
                            select="translate(@noinstall, 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')"/>
                        <xsl:choose>
                            <xsl:when test="$noinstall_upr = 'TRUE'">
                                <xsl:attribute name="action">
                                    <xsl:text>noinstall</xsl:text>
                                </xsl:attribute>
                            </xsl:when>
                        </xsl:choose>
                    </xsl:if>

                    <xsl:if test="@name">
                        <!-- If pkg name was a comma-separated list, break it up into pkg names. -->
                        <xsl:call-template name="package_name_list">
                            <xsl:with-param name="str" select="@name"/>
                            <xsl:with-param name="splitString" select="','"/>
                        </xsl:call-template>
                    </xsl:if>
                </software_data>
            </xsl:if>
        </software>
    </xsl:template>

    <xsl:template match="searchall">
        <search_all>
            <xsl:if test="@addall">
                <xsl:attribute name="addall">
                    <xsl:value-of select="@addall"/>
                </xsl:attribute>
            </xsl:if>

            <xsl:if test="@location or @publisher">
                <source>
                    <publisher>
                        <xsl:if test="@publisher">
                            <xsl:attribute name="name">
                                <xsl:value-of select="@publisher"/>
                            </xsl:attribute>
                        </xsl:if>

                        <xsl:if test="@location">
                            <origin>
                                <xsl:attribute name="name">
                                    <xsl:value-of select="@location"/>
                                </xsl:attribute>
                            </origin>
                        </xsl:if>
                    </publisher>
                </source>
            </xsl:if>
        </search_all>
    </xsl:template>


    <!-- Handle sc_embedded_manifest, where ai_manifest is *not* present. -->
    <!-- NB: this output won't validate, but may be of some when porting. -->
    <xsl:template match="sc_embedded_manifest">
        <xsl:if test="not(../ai_embedded_manifest/ai_manifest)">
            <ai_instance name="auto_install">
                <xsl:copy-of select="."/>
            </ai_instance>
        </xsl:if>
    </xsl:template>



    <!-- Recursive tokenizing template for splitting a -->
    <!-- comma-separated list of packages names into a -->
    <!-- list of name elements. -->
    <!-- Written by David Pawson, found at: -->
    <!-- http://www.oxygenxml.com/archives/xsl-list/200504/msg00939.html -->

    <xsl:template name="package_name_list">
        <xsl:param name="str" select="."/>
        <xsl:param name="splitString" select="','"/>
        <xsl:choose>
            <xsl:when test="contains($str,$splitString)">
                <name>
                    <xsl:value-of select="normalize-space(substring-before($str,$splitString))"/>
                </name>
                <xsl:call-template name="package_name_list">
                    <xsl:with-param name="str" select="substring-after($str,$splitString)"/>
                    <xsl:with-param name="splitString" select="$splitString"/>
                </xsl:call-template>
            </xsl:when>
            <xsl:otherwise>
                <name><xsl:value-of select="normalize-space($str)"/></name>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
</xsl:stylesheet>
