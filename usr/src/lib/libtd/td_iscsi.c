/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at usr/src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */
/*
 * Copyright (c) 2009, 2010, Oracle and/or its affiliates. All rights reserved.
 */

#include <ima.h> /* Needed by IMA functions */
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <strings.h>
#include <ls_api.h>
#include <widec.h>
#include <unistd.h>
#include <errno.h>
#include <sys/param.h>

#include	"td_api.h"

#define	INSTISCSI_MAX_RETRY_TIME	6
#define	INSTISCSI_SLEEP_INTERVAL	5
#define	INSTISCSI_DEFAULT_DEST_PORT	3260
#define	INSTISCSI_MIN_CHAP_LEN		12

static td_errno_t instiscsi_add_static_config(char *targetname,
    char *ipaddress, unsigned long port);
static td_errno_t instiscsi_modify_static_discovery(IMA_BOOL enable);
static td_errno_t instiscsi_get_device_name_via_tgtname(
    char *target_name, char *str_num, char *p_name, int buf_size);
static td_errno_t instiscsi_set_chap(char *chap_secret, char *chap_name);
static td_errno_t instiscsi_set_initiator_node_name(char *node_name);

/*
 * Helper function
 *
 * return 0: success
 *       -1: failure
 */
static int
instiscsi_get_initiator_oid(IMA_OID *oid)
{
	IMA_OID_LIST	*lhbalist	= NULL;
	IMA_STATUS status = IMA_GetLhbaOidList(&lhbalist);

	if (!IMA_SUCCESS(status)) {
		td_debug_print(LS_DBGLVL_ERR,
		    "get iSCSI initiator list failed\n");
		return (-1);
	}

	if (lhbalist == NULL || lhbalist->oidCount == 0) {
		if (lhbalist != NULL)
			(void) IMA_FreeMemory(lhbalist);
		return (-1);
	}

	/* We only have one initiator for one node */
	*oid = lhbalist->oids[0];
	(void) IMA_FreeMemory(lhbalist);

	return (0);
}

/*
 * Function:    instiscsi_add_static_config()
 * Description: Add a static-config to the iscsi driver.
 *		If port is zero, 3260 will be used.
 * Parameters:
 *      	targetname	-	target name
 *		ipaddress	-	ip address
 *		port		-	dest port
 *
 * Return:  	td_errno_t
 *
 * Status:
 *      internal
 */
static td_errno_t
instiscsi_add_static_config(char *targetname, char *ipaddress,
    unsigned long port)
{
	IMA_OID				oid;
	IMA_STATUS			status;
	IMA_OID_LIST			*statictargetlist;
	IMA_STATIC_DISCOVERY_TARGET	statictgtconfig;
	IMA_STATIC_DISCOVERY_TARGET_PROPERTIES	targetprops;

	char	targetipaddr[INSTISCSI_IP_ADDRESS_LEN]	= {0};
	char	tmpstr[INSTISCSI_IP_ADDRESS_LEN]	= {0};
	char	*p		    = NULL;
	int	i		    = 0;
	int	ret		    = 0;

	if (targetname == NULL || ipaddress == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "Required target name or "
		    "IP address missing.\n");
		return (TD_E_INVALID_ARG);
	}

	ret = instiscsi_get_initiator_oid(&oid);
	if (ret != 0) {
		td_debug_print(LS_DBGLVL_ERR, "Initiator OID not found\n");
		return (TD_E_NOT_FOUND);
	}

	if (port == 0) {
		port = INSTISCSI_DEFAULT_DEST_PORT;
	}
	/*
	 * Currently iscsi driver doesn't allow to add a duplicated
	 * static configuration. So we try to get the existed static
	 * configuration first and do a comparision. If the configuration
	 * exists, we just return with success.
	 */
	status = IMA_GetStaticDiscoveryTargetOidList(oid,
	    &statictargetlist);
	if (!IMA_SUCCESS(status)) {
		td_debug_print(LS_DBGLVL_ERR,
		    "failed to get static static target oid list\n");
	}

	/*
	 * Copy the target name and ipaddress to statictgtconfig. We will
	 * use it to do the comparision later.
	 */
	(void) mbstowcs(statictgtconfig.targetName, targetname,
	    IMA_NODE_NAME_LEN);

	(void) sprintf(targetipaddr, "%s:%lu", ipaddress, port);

	(void) mbstowcs(statictgtconfig.targetAddress.hostnameIpAddress.
	    id.hostname, targetipaddr, IMA_HOST_NAME_LEN);

	for (i = 0; i < statictargetlist->oidCount; i++) {
		(void) memset(&targetprops, 0, sizeof (targetprops));

		status = IMA_GetStaticDiscoveryTargetProperties(
		    statictargetlist->oids[i], &targetprops);
		if (!IMA_SUCCESS(status)) {
			td_debug_print(LS_DBGLVL_ERR, "failed to get static "
			    "discovery target properties.\n");
			continue;
		}
		/*
		 * Compare the target name.
		 */
		ret = wcscmp(statictgtconfig.targetName,
		    targetprops.staticTarget.targetName);
		if (ret != 0) {
			continue;
		}

		/*
		 * Compare the target ip address.
		 */
		(void) memset(tmpstr, 0, sizeof (tmpstr));
		(void) wcstombs(tmpstr, targetprops.staticTarget.targetAddress.
		    hostnameIpAddress.id.hostname, sizeof (tmpstr));

		p = strchr(tmpstr, ':');
		if (p != NULL) {
			*p = '\0';
		}

		ret = strcmp(ipaddress, tmpstr);
		if (ret != 0) {
			continue;
		}

		/*
		 * Compare dest port.
		 */
		if (p != NULL) {
			*p = ':';
			ret = strcmp(targetipaddr, tmpstr);
			if (ret != 0) {
				/*
				 * Dest port is different. Here we remove
				 * the existed one and then add the new
				 * configuration.
				 */
				status = IMA_RemoveStaticDiscoveryTarget(
				    statictargetlist->oids[i]);
				if (!IMA_SUCCESS(status)) {
					return (TD_E_LUN_BUSY);
				}
				break;
			}
		}
		/*
		 * Target name, ipaddress and port are all same. No need to add
		 * a duplicated one. Return with success.
		 */
		return (TD_E_SUCCESS);
	}

	status = IMA_AddStaticDiscoveryTarget(oid, statictgtconfig, &oid);
	if (!IMA_SUCCESS(status)) {
		td_debug_print(LS_DBGLVL_ERR, "iSCSI add static discovery "
		    "target failed.\n");
		return (TD_E_NOT_FOUND);
	}
	return (TD_E_SUCCESS);
}

/*
 * Function:    instiscsi_modify_static_discovery()
 * Description: Modify the static discovery. It will enable the discovery
 *		if enable is IMA_TRUE. Otherwise, it will disable the
 *		static discovery.
 * Parameters:
 *      enable        -		IMA_FALSE or IMA_TRUE
 * Return:      td_errno_t
 *
 * Status:
 *      internal
 */
static td_errno_t
instiscsi_modify_static_discovery(IMA_BOOL enable)
{
	IMA_OID	oid;
	int	ret;
	IMA_STATUS status;

	ret = instiscsi_get_initiator_oid(&oid);
	if (ret != 0) {
		td_debug_print(LS_DBGLVL_ERR, "Initiator OID not found\n");
		return (TD_E_NOT_FOUND);
	}

	status = IMA_SetStaticDiscovery(oid, enable);
	if (!IMA_SUCCESS(status)) {
		td_debug_print(LS_DBGLVL_ERR,
		    "iSCSI SetStaticDiscovery failed\n");
		return (TD_E_NOT_FOUND);
	}
	/*
	 * Wait for a while here for updating.
	 */
	(void) sleep(INSTISCSI_SLEEP_INTERVAL * 2);

	return (TD_E_SUCCESS);
}
static int
parse_lun_num(char *str_num, void *hex_num, int length)
{
	char	    *p	= NULL;
	uint16_t    *conv_num = (uint16_t *)hex_num;
	long	    tmp	= 0;
	int	    i	= 0;

	if (str_num == NULL || hex_num == NULL || length < 8) {
		return (-1);
	}

	bzero((void *)hex_num, 8);

	for (i = 0; i < 4; i++) {
		p = NULL;
		p = strchr((const char *)str_num, '-');
		if (p != NULL) {
			*p = '\0';
		}
		tmp = strtol((const char *)str_num, NULL, 16);
		if (tmp == 0 && (errno == ERANGE || errno == EINVAL)) {
			return (-1);
		}
		conv_num[i] = (uint16_t)tmp;
		if (p != NULL) {
			str_num = p + 1;
		} else {
			break;
		}
	}
	return (0);
}

/*
 * Function:    instiscsi_get_device_name_via_tgtname()
 * Description: Get the os device name according to the target and lun number.
 *		The name will be placed in p_ame. Its format is
 *		/dev/rdsk/cxxxtxxxx...s2.
 *		The caller should supply the space in p_name.
 *		If there is no lun specified, str_num can be set to NULL.
 *		And the name of LUN 0 will be returned.
 * Parameters:
 *       target_name       - target name
 *	 str_num	   - lun number
 *	 p_name		   - buffer
 *	 buf_size	   - buffer size
 * Return:      td_errno_t
 *
 * Status:
 *      internal
 */
static td_errno_t
instiscsi_get_device_name_via_tgtname(char *target_name, char *str_num,
    char *p_name, int buf_size)
{
	IMA_OID			oid;
	IMA_OID_LIST		*ptgt_list	= NULL;
	IMA_OID_LIST		*plun_list	= NULL;
	IMA_STATUS		status;
	IMA_LU_PROPERTIES	lun_prop;
	IMA_WCHAR		tmp_name[IMA_NODE_NAME_LEN] = {0};
	IMA_TARGET_PROPERTIES	tgt_prop;

	int			i	    = 0;
	int			ret	    = 0;
	int			found	    = 0;
	int			retry	    = 0;
	uint16_t		lun_num	    = 0;
	uint16_t		hex_num[4]  = {0};

	if (p_name == NULL || buf_size == 0 || target_name == NULL) {
		return (TD_E_INVALID_PARAMETER);
	}

	if (str_num != NULL) {
		ret = parse_lun_num(str_num, hex_num, 8);
		if (ret != 0) {
			return (TD_E_NOT_FOUND);
		}
		lun_num = hex_num[0];
	}

	ret = instiscsi_get_initiator_oid(&oid);
	if (ret != 0) {
		return (TD_E_NOT_FOUND);
	}

	/*
	 * Compare target name.
	 */
	status = IMA_GetTargetOidList(oid, &ptgt_list);
	if (!IMA_SUCCESS(status)) {
		td_debug_print(LS_DBGLVL_ERR, "Get Target OID list failed.\n");
		return (TD_E_UNKNOWN_IMA_ERROR);
	}

	(void) mbstowcs(tmp_name, target_name, IMA_NODE_NAME_LEN);
	for (i = 0; i < ptgt_list->oidCount; i++) {
		(void) memset(&tgt_prop, 0, sizeof (tgt_prop));
		status = IMA_GetTargetProperties(ptgt_list->oids[i],
		    &tgt_prop);
		if (!IMA_SUCCESS(status)) {
			continue;
		}

		ret = wcscmp(tmp_name, tgt_prop.name);
		if (ret == 0) {
			found = 1;
			break;
		}
	}

	if (found == 0) {
		free(ptgt_list);
		return (TD_E_NOT_FOUND);
	}

	/*
	 * Compare the lun number.
	 */
	status = IMA_GetLuOidList(ptgt_list->oids[i], &plun_list);
	if (!IMA_SUCCESS(status)) {
		td_debug_print(LS_DBGLVL_ERR, "Get LUN oid list failed\n");
		return (TD_E_NOT_FOUND);
	}
	found = 0;
	i = 0;
	while (i < plun_list->oidCount) {
		bzero(&lun_prop, sizeof (lun_prop));
		status = IMA_GetLuProperties(plun_list->oids[i], &lun_prop);
		if (!IMA_SUCCESS(status)) {
			i++;
			continue;
		}

		if (lun_num == (uint16_t)lun_prop.targetLun) {
			if (lun_prop.osDeviceNameValid == IMA_TRUE) {
				(void) wcstombs(p_name,
				    lun_prop.osDeviceName, buf_size);
				found = 1;
				break;
			} else if (retry <= INSTISCSI_MAX_RETRY_TIME) {
				/*
				 * Sometimes Solaris doesn't have enough
				 * time to generate os device name. So wait
				 * for a while here.
				 */
				retry++;
				(void) sleep(INSTISCSI_SLEEP_INTERVAL);
				continue;
			} else {
				break;
			}
		} else {
			i++;
		}
	}

	free(ptgt_list);
	free(plun_list);

	if (found == 0) {
		ret = TD_E_NOT_FOUND;
	}
	return (ret);
}

/*
 * Function:	iscsi_static_config(attribute list)
 * Description:	Perform an iSCSI static target configuration
 *
 * Parameters:	attrs
 *
 * 	Given attributes:
 *		TD_ISCSI_ATTR_NAME - iSCSI target name
 *		TD_ISCSI_ATTR_IP - iSCSI target IP address
 *		TD_ISCSI_ATTR_PORT - iSCSI target port
 *		TD_ISCSI_ATTR_LUN - iSCSI target LUN
 * 	Return attribute:
 *		TD_ISCSI_ATTR_DEVICE_NAME - device name in format:
 *			/dev/rdsk/cXtXdXs2
 * Return: TD error code
 * Status:
 *	public
 */
td_errno_t
iscsi_static_config(nvlist_t *attrs)
{
	char *target_name, *ip_address, *lun_num = "";
	int buf_size;
	uint32_t port = 0;
	char devnam[INSTISCSI_MAX_OS_DEV_NAME_LEN + 1] = {0};
	td_errno_t status;

	if (nvlist_lookup_string(attrs, TD_ISCSI_ATTR_NAME, &target_name) !=
	    0) {
		td_debug_print(LS_DBGLVL_ERR, "missing iSCSI target name\n");
		return (TD_E_INVALID_PARAMETER);
	}
	if (nvlist_lookup_string(attrs, TD_ISCSI_ATTR_IP, &ip_address) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "missing iSCSI IP address\n");
		return (TD_E_INVALID_PARAMETER);
	}
	(void) nvlist_lookup_uint32(attrs, TD_ISCSI_ATTR_PORT, &port);
	/*
	 * specify iSCSI parameters for static configuration
	 */
	status = instiscsi_add_static_config(target_name, ip_address, port);
	if (status != TD_E_SUCCESS) {
		return (status);
	}
	/*
	 * enable static discovery in initiator
	 */
	status = instiscsi_modify_static_discovery(IMA_TRUE);
	if (status != TD_E_SUCCESS) {
		return (status);
	}
	if (nvlist_lookup_pairs(attrs, NV_FLAG_NOENTOK,
	    TD_ISCSI_ATTR_LUN, DATA_TYPE_STRING, &lun_num, NULL) != 0) {
		td_debug_print(LS_DBGLVL_ERR,
		    "Error in lookup of iSCSI LUN\n");
		return (TD_E_INVALID_PARAMETER);
	}
	/*
	 * given iSCSI target name and LUN, return Solaris device name
	 */
	status = instiscsi_get_device_name_via_tgtname(target_name, lun_num,
	    devnam, sizeof (devnam));
	if (status != TD_E_SUCCESS) {
		td_debug_print(LS_DBGLVL_ERR, "iSCSI target not found "
		    "with given target parameters.\n");
		return (status);
	}
	/*
	 * return Solaris device name
	 */
	if (devnam[0] == '\0') {
		td_debug_print(LS_DBGLVL_ERR, "couldn't find iSCSI target\n");
		return (TD_E_NOT_FOUND);
	}
	if (nvlist_add_string(attrs,
	    TD_ISCSI_ATTR_DEVICE_NAME, devnam) != 0) {
		td_debug_print(LS_DBGLVL_ERR,
		    "couldn't add $iSCSI target name\n");
		return (TD_E_INVALID_PARAMETER);
	}
	return (TD_E_SUCCESS);
}

/*
 * Set iscsi initiator node name.  Optional, for CHAP support
 */
/*
 * Function: 	instiscsi_set_initiator_node_name()
 * Description: Set iscsi initiator node name.  Optional, for CHAP support
 *
 * Parameters:
 *      node_name       -
 * Return:      td_errno_t
 *
 * Status:
 *      internal
 */
static td_errno_t
instiscsi_set_initiator_node_name(char *node_name)
{
	int		ret = 0;
	IMA_NODE_NAME	newname;
	IMA_STATUS	status;
	IMA_OID		oid;

	if (node_name == NULL || strlen(node_name) >= IMA_NODE_NAME_LEN) {
		return (TD_E_INVALID_PARAMETER);
	}
	ret = instiscsi_get_initiator_oid(&oid);
	if (ret != 0) {
		return (TD_E_UNKNOWN_IMA_ERROR);
	}

	(void) memset(&newname, 0, sizeof (IMA_NODE_NAME));
	(void) mbstowcs(newname, node_name, IMA_NODE_NAME_LEN);

	oid.objectType = IMA_OBJECT_TYPE_NODE;
	status = IMA_SetNodeName(oid, newname);
	if (!IMA_SUCCESS(status)) {
		return (TD_E_UNKNOWN_IMA_ERROR);
	}
	return (TD_E_SUCCESS);
}

/*
 * Function:    instiscsi_set_chap()
 * Description: Set the CHAP secret and name. The CHAP secret length must be
 *		between 12 to 16.
 * Parameters:
 *       charp_secret       - chap secret
 *	 chap_name	    - chap user name
 * Return:      td_errno_t
 *
 * Status:
 *      internal
 */
static td_errno_t
instiscsi_set_chap(char *chap_secret, char *chap_name)
{
	int		ret	    = 0;
	int		secret_len  = 0;
	int		name_len    = 0;

	IMA_OID			oid;
	IMA_INITIATOR_AUTHPARMS	authparams;
	IMA_AUTHMETHOD		methodlist[1];
	IMA_UINT		methodcount = 1;
	IMA_STATUS		status;
	IMA_AUTHMETHOD		value	    = IMA_AUTHMETHOD_CHAP;

	if (chap_secret == NULL || chap_name == NULL) {
		return (TD_E_INVALID_PARAMETER);
	}

	secret_len = strlen(chap_secret);
	name_len = strlen(chap_name);
	if (secret_len < INSTISCSI_MIN_CHAP_LEN ||
	    secret_len > INSTISCSI_MAX_CHAP_LEN ||
	    name_len <= 0 ||
	    name_len > INSTISCSI_MAX_CHAP_NAME_LEN) {
		return (TD_E_INVALID_PARAMETER);
	}

	ret = instiscsi_get_initiator_oid(&oid);
	if (ret != 0) {
		return (TD_E_UNKNOWN_IMA_ERROR);
	}
	/*
	 * Set CHAP method for authentication.
	 */
	methodlist[0] = value;
	status = IMA_SetInitiatorAuthMethods(oid, methodcount, &methodlist[0]);
	if (!IMA_SUCCESS(status)) {
		return (TD_E_UNKNOWN_IMA_ERROR);
	}

	status = IMA_GetInitiatorAuthParms(oid, value,
	    &authparams);
	if (!IMA_SUCCESS(status)) {
		return (TD_E_UNKNOWN_IMA_ERROR);
	}
	(void) memset(&authparams.chapParms.name, 0,
	    sizeof (authparams.chapParms.name));
	(void) memcpy(&authparams.chapParms.name,
	    &chap_name[0], name_len);
	authparams.chapParms.nameLength = name_len;

	(void) memset(&authparams.chapParms.challengeSecret, 0,
	    sizeof (authparams.chapParms.challengeSecret));
	(void) memcpy(&authparams.chapParms.challengeSecret,
	    &chap_secret[0], secret_len);
	authparams.chapParms.challengeSecretLength = secret_len;

	status = IMA_SetInitiatorAuthParms(oid, IMA_AUTHMETHOD_CHAP,
	    &authparams);
	if (!IMA_SUCCESS(status)) {
		return (TD_E_UNKNOWN_IMA_ERROR);
	}
	return (TD_E_SUCCESS);
}
