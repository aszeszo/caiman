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
 * Copyright (c) 2007, 2010, Oracle and/or its affiliates. All rights reserved.
 */

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <math.h>
#include <glib/gi18n.h>
#include "string.h"

#include "orchestrator-wrappers.h"

#define	NODEFAULTLANGLABEL N_("No default language support")

static float
round_up_to_tenths(float value)
{
	float newval;

	newval = roundf((value)*10.0) / 10.0;
	if (newval < value)
		newval += 0.1;
	return (newval);
}

disk_info_t **
orchestrator_om_get_disk_info(
    om_handle_t handle,
    gint *numdisks)
{
	gint numberofdisks = 0;
	disk_info_t **alldiskinfo = NULL;
	disk_info_t *infoptr = om_get_disk_info(handle, &numberofdisks);
	alldiskinfo = om_convert_linked_disk_info_to_array(handle,
	    infoptr,
	    numberofdisks);
	*numdisks = numberofdisks;
	return (alldiskinfo);
}

disk_info_t *
orchestrator_om_duplicate_disk_info(disk_info_t *dinfo)
{
	g_return_val_if_fail(dinfo != NULL, NULL);
	return (om_duplicate_disk_info(omhandle, dinfo));
}

gint
orchestrator_om_get_numparts_of_type(
    disk_parts_t *partitions,
    guint partitiontype)
{
	partition_info_t *partition;
	gint numfound = 0;
	int i;

	g_return_val_if_fail(partitions != NULL, -1);

	for (i = 0; i < OM_NUMPART; i++) {
		partition = &partitions->pinfo[i];
		if (orchestrator_om_get_partition_type(partition) ==
		    partitiontype) {
			if (partitiontype != SUNIXOS)
				numfound++;
			/*
			 * Since this could also be a linux swap,
			 * check content type.
			 */
			else if (partition->content_type != OM_CTYPE_LINUXSWAP)
				numfound++;
		}
	}
	return (numfound);
}

disk_parts_t *
orchestrator_om_partitions_dup(disk_parts_t *partitions)
{
	g_return_val_if_fail(partitions != NULL, NULL);
	return (om_duplicate_disk_partition_info(omhandle, partitions));
}

disk_parts_t *
orchestrator_om_get_disk_partitions(
    om_handle_t handle,
    gchar *diskname)
{
	return (om_get_disk_partition_info(handle, diskname));
}

gint
orchestrator_om_get_free_spacegb(
    om_handle_t handle,
    disk_info_t *diskinfo,
    gfloat *freespace)
{
	disk_parts_t *partitions;
	partition_info_t *partition;
	gfloat capacity = 0;
	gfloat usage = 0;
	int i;

	if (!diskinfo || !diskinfo->disk_name)
		return (-1);

	partitions = orchestrator_om_get_disk_partitions(handle,
	    diskinfo->disk_name);
	capacity = orchestrator_om_get_disk_sizegb(diskinfo);
	for (i = 0; i < FD_NUMPART; i++) {
		partition = &partitions->pinfo[i];
		usage += orchestrator_om_get_partition_sizegb(partition);
	}
	*freespace = capacity - usage;
	return (0);
}

gint
orchestrator_om_get_max_partition_id(disk_parts_t *partitions)
{
	partition_info_t *partition = NULL;
	gint numfound = 0;

	g_return_val_if_fail(partitions != NULL, -1);

	/* There can be gaps in the pinfo table for partitions so */
	/* cycle through all partitions, and get the largest value for */
	/* partition_id */
	for (gint i = 0; i < OM_NUMPART; i++) {
		partition = &partitions->pinfo[i];
		if ((partition->partition_id > 0) &&
		    (partition->partition_id <= OM_NUMPART) &&
		    (numfound < partition->partition_id))
			numfound = partition->partition_id;
	}
	return (numfound);
}

partition_info_t *
orchestrator_om_get_part_by_partition_id(
    disk_parts_t *partitions,
    guint partid)
{
	gint i;
	gint numparts = 0;

	g_return_val_if_fail(partitions != NULL, NULL);
	g_return_val_if_fail(
	    ((partid > (guint)0) && (partid <= OM_NUMPART)), NULL);

	for (i = 0; i < OM_NUMPART; i++) {
		if (partitions->pinfo[i].partition_id == partid) {
			return (&partitions->pinfo[i]);
		}
	}
	return (NULL);
}

partition_info_t *
orchestrator_om_get_part_by_blkorder(
    disk_parts_t *partitions,
    guint order)
{
	gint i;
	gint numparts = 0;

	g_return_val_if_fail(partitions != NULL, NULL);
	g_return_val_if_fail(
	    ((order >= (guint)0) && (order < OM_NUMPART)), NULL);

	for (i = 0; i < OM_NUMPART; i++) {
		/* Block order determined by partition_order */
		/* Use partition_order */
		if (partitions->pinfo[i].partition_order == order+1) {
			return (&partitions->pinfo[i]);
		}
	}
	return (NULL);
}

void
orchestrator_om_set_partition_info(
	partition_info_t *partinfo,
	uint32_t size,
	uint32_t offset,
	uint64_t size_sec,
	uint64_t offset_sec)
{
	partinfo->partition_id = 0;
	partinfo->partition_size = size;
	partinfo->partition_offset = offset;
	partinfo->partition_order = 0;
	partinfo->partition_type = UNUSED;
	partinfo->content_type = OM_CTYPE_UNKNOWN;
	partinfo->active = B_FALSE;
	partinfo->partition_size_sec = size_sec;
	partinfo->partition_offset_sec = offset_sec;
}

/* Find the first available primary partition and initialise it */
partition_info_t *
orchestrator_om_find_unused_primary_partition(
    disk_parts_t *partitions,
    guint partitiontype,
    gint order)
{
	partition_info_t *partition = NULL;
	gint first_unused_id = 0;

	g_return_val_if_fail(partitions != NULL, NULL);
	g_return_val_if_fail((order >= 0) && (order < FD_NUMPART), NULL);

	/*
	 * Find the lowest numbered primary partition ID that's not in use by
	 * an existing partition
	 */
	for (gint i = 0; i < FD_NUMPART; i++) {
		gint j;

		for (j = 0; j < FD_NUMPART; j++) {
			if (partitions->pinfo[j].partition_id == i + 1)
				break;
		}

		if (j == FD_NUMPART) {
			first_unused_id = i + 1;
			break;
		}
	}

	if (first_unused_id == 0) {
		g_warning(
		    "Device %s already has all %d primary partitions in use",
		    partitions->disk_name, FD_NUMPART);
	}

	/* Find the first available slot in the pinfo array */
	for (gint i = 0; i <  FD_NUMPART; i++) {
		partition = &partitions->pinfo[i];
		if (partition->partition_type == UNUSED &&
		    partition->partition_order < 1) {
			partition->partition_type = partitiontype;
			partition->partition_order = order+1;
			partition->partition_id = first_unused_id;
			g_debug("Free position found for partition %d: "
			    "order=%d, slot=%d", i, order, first_unused_id);
			return (partition);
		}
	}
	return (NULL);
}


gint
orchestrator_om_get_last_logical_index(
	disk_parts_t *partitions)
{
	partition_info_t *partinfo = NULL;
	gint lidx = 0;

	for (lidx = FD_NUMPART; lidx < OM_NUMPART; lidx++) {
		partinfo =
		    orchestrator_om_get_part_by_blkorder(partitions, lidx);
		if (!partinfo) {
			break;
		}
	}

	return (lidx);
}

/* Find the first available logical partition and initialise it */
partition_info_t *
orchestrator_om_find_unused_logical_partition(
    disk_parts_t *partitions,
    guint partitiontype,
    gint order)
{
	partition_info_t *partition = NULL;
	gint first_unused_id = 0;

	g_return_val_if_fail(partitions != NULL, NULL);
	g_return_val_if_fail(
	    (order >= 0) && (order < OM_NUMPART), NULL);

	/*
	 * Find the lowest numbered partition ID that's not in use by
	 * an existing partition
	 */
	for (gint i = FD_NUMPART; i < OM_NUMPART; i++) {
		gint j;

		for (j = FD_NUMPART; j < OM_NUMPART; j++) {
			if (partitions->pinfo[j].partition_id == i + 1)
				break;
		}

		if (j == OM_NUMPART) {
			first_unused_id = i + 1;
			break;
		}
	}

	if (first_unused_id == 0) {
		g_warning(
		    "Device %s already has all %d logical partitions in use",
		    partitions->disk_name, MAX_EXT_PARTS);
	}

	/* Find the first available slot in the pinfo array */
	for (gint i = FD_NUMPART; i <  OM_NUMPART; i++) {
		partition = &partitions->pinfo[i];
		if (partition->partition_type == UNUSED &&
		    partition->partition_order < 1) {
			partition->partition_type = partitiontype;
			partition->partition_order = order+1;
			partition->partition_id = first_unused_id;
			g_debug("Free position found for partition %d: "
			    "order=%d, slot=%d", i, order, first_unused_id);
			return (partition);
		}
	}
	return (NULL);
}

guint
orchestrator_om_get_partition_type(partition_info_t *partition)
{
	g_return_val_if_fail(partition, -1);
	return (partition->partition_type);
}

void
orchestrator_om_set_partition_type(
    partition_info_t *partition,
    guint type)
{
	g_return_if_fail(partition != NULL);
	partition->partition_type = type;
}

guint64
orchestrator_om_get_partition_sizemb(partition_info_t *partition)
{
	g_return_val_if_fail(partition != NULL, -1);
	return ((guint64)partition->partition_size);
}

void
orchestrator_om_set_partition_sizemb(
    partition_info_t *partition,
    guint64 size)
{
	g_return_if_fail(size >= (guint)0);
	if (partition)
		partition->partition_size = (uint64_t)size;
}

gfloat
orchestrator_om_get_partition_sizegb(partition_info_t *partition)
{
	g_return_val_if_fail(partition != NULL, (gfloat)-1);
	return (partition->partition_size > 0 ?
	    (gfloat)partition->partition_size/MBPERGB : 0);
}

gfloat
orchestrator_om_round_mbtogb(uint32_t sizemb)
{
	gchar *sizembstr = NULL;
	gfloat retsize = 0;

	sizembstr = g_strdup_printf("%.1f",
	    sizemb > 0 ? (gfloat)sizemb/MBPERGB : 0);
	retsize = atof(sizembstr);
	g_free(sizembstr);

	return (retsize);
}

uint32_t
orchestrator_om_gbtomb(gfloat sizegb)
{
	gfloat newsize;

	newsize = sizegb * MBPERGB;
	return ((uint32_t)newsize);
}

void
orchestrator_om_set_partition_sizegb(
    partition_info_t *partition,
    gfloat size)
{
	/* convert GB to MB (1024MB = 1GB) */
	g_return_if_fail(size >= 0);
	if (partition)
		partition->partition_size = orchestrator_om_gbtomb(size);
}

gchar *
orchestrator_om_get_disk_type(disk_info_t *diskinfo)
{
	gchar *type = NULL;
	g_return_val_if_fail(diskinfo != NULL, NULL);

	switch (diskinfo->disk_type) {
		case OM_DTYPE_ATA:
			type = g_strdup(_("ATA"));
			break;
		case OM_DTYPE_SCSI:
			type = g_strdup(_("SCSI"));
			break;
		case OM_DTYPE_FIBRE:
			type = g_strdup(_("Fibre"));
			break;
		case OM_DTYPE_USB:
			type = g_strdup(_("USB"));
			break;
		case OM_DTYPE_SATA:
			type = g_strdup(_("SATA"));
			break;
		case OM_DTYPE_FIREWIRE:
			type = g_strdup(_("IEEE1394"));
		default:
			type = g_strdup(_("Unknown"));
			break;
	}
	return (type);
}

void
orchestrator_om_set_disk_label(
    disk_info_t *diskinfo,
    om_disklabel_type_t type)
{
	g_return_if_fail(diskinfo != NULL);
	diskinfo->label = type;
}

guint64
orchestrator_om_get_disk_sizemb(disk_info_t *dinfo)
{
	g_return_val_if_fail(dinfo != NULL, -1);
	return (dinfo->disk_size);
}

guint64
orchestrator_om_get_total_disk_sizemb(disk_info_t *dinfo)
{
	g_return_val_if_fail(dinfo != NULL, -1);
	return (dinfo->disk_size_total);
}

gfloat
orchestrator_om_get_disk_sizegb(disk_info_t *dinfo)
{
	g_return_val_if_fail(dinfo != NULL, (gfloat)-1);
	return ((gfloat)(dinfo->disk_size)/MBPERGB);
}

gfloat
orchestrator_om_get_total_disk_sizegb(disk_info_t *dinfo)
{
	g_return_val_if_fail(dinfo != NULL, (gfloat)-1);
	return ((gfloat)(dinfo->disk_size_total)/MBPERGB);
}

const gchar*
orchestrator_om_get_disk_devicename(disk_info_t *diskinfo)
{
	g_return_val_if_fail(diskinfo != NULL, NULL);
	return (diskinfo->disk_name);
}

const gchar*
orchestrator_om_get_disk_vendor(disk_info_t *diskinfo)
{
	g_return_val_if_fail(diskinfo != NULL, NULL);
	return (diskinfo->vendor);
}

gboolean
orchestrator_om_disk_is_bootdevice(disk_info_t *diskinfo)
{
	g_return_val_if_fail(diskinfo != NULL, FALSE);
	return (diskinfo->boot_disk);
}

guint64
orchestrator_om_get_mininstall_sizemb(void)
{
	return (guint64)om_get_min_size(NULL, NULL);
}

gfloat
orchestrator_om_get_mininstall_sizegb(gboolean roundup)
{
	gfloat minsize;

	minsize = ((gfloat)om_get_min_size(NULL, NULL)/MBPERGB);
	if (roundup == FALSE)
		return (minsize);
	else
		return ((gfloat)round_up_to_tenths(minsize));
}

guint64
orchestrator_om_get_recommended_sizemb(void)
{
	return (guint64)om_get_recommended_size(NULL, NULL);
}

guint64
orchestrator_om_get_recommended_sizegb(void)
{
	return (((guint64)om_get_recommended_size(NULL, NULL) + MBPERGB / 2) /
	    MBPERGB);
}

gint
orchestrator_om_get_upgrade_targets_by_disk(
    disk_info_t *dinfo,
    upgrade_info_t **uinfo,
    guint16 *found)
{
	*uinfo = om_get_upgrade_targets_by_disk(
	    omhandle, dinfo->disk_name, found);
	return (0);
}

upgrade_info_t *
orchestrator_om_duplicate_upgrade_targets(upgrade_info_t *uinfo)
{
	return (om_duplicate_upgrade_targets(omhandle, uinfo));
}

gboolean
orchestrator_om_is_upgrade_target(upgrade_info_t *uinfo)
{
	if (uinfo)
		return (uinfo->upgradable);
	else
		return (FALSE);
}

/*
 * Performs a dry run to ensure the upgrade target has
 * enough free space for the upgrade.
 * Caller should first call orchestrator_om_is_upgrade_target()
 * to ensure it's an upgrade target.
 */
void
orchestrator_om_is_upgrade_target_valid(upgrade_info_t *uinfo,
    om_callback_t callback)
{
	g_return_if_fail(uinfo->upgradable != B_FALSE);
	om_is_upgrade_target_valid(omhandle, uinfo, callback);
}

gchar *
orchestrator_om_upgrade_instance_get_diskname(upgrade_info_t *uinfo)
{
	if (uinfo && uinfo->instance_type == OM_INSTANCE_UFS)
		return (uinfo->instance.uinfo.disk_name);
	else
		return (NULL);
}

gchar *
orchestrator_om_upgrade_instance_construct_slicename(upgrade_info_t *uinfo)
{
	if (uinfo && uinfo->instance_type == OM_INSTANCE_UFS) {
		g_assert(uinfo->instance.uinfo.disk_name != NULL);
		return (g_strdup_printf(_("%ss%d"),
		    uinfo->instance.uinfo.disk_name,
		    uinfo->instance.uinfo.slice));
	} else
		return (NULL);
}

gint
orchestrator_om_upgrade_instance_get_slicenum(upgrade_info_t *uinfo)
{
	if (uinfo && uinfo->instance_type == OM_INSTANCE_UFS)
		return (uinfo->instance.uinfo.slice);
	else
		return (NULL);
}

upgrade_info_t *
orchestrator_om_upgrade_instance_get_next(upgrade_info_t *uinfo)
{
	if (!uinfo)
		return (NULL);
	else
		return (uinfo->next);
}

gchar *
orchestrator_om_upgrade_instance_get_release_name(upgrade_info_t *uinfo)
{
	if (!uinfo)
		return (NULL);
	else
		return (uinfo->solaris_release);
}

/* language stuff */
static locale_info_t cposix = {
	"C",
	N_("C/POSIX"),
	B_TRUE,
	NULL
};

static lang_info_t nodefault = {
	&cposix,
	B_FALSE,
	NULL, /* translated string to be set later */
	1,
	NULL, /* translated string to be set later */
	NULL
};

static gint
language_cmp(
    gconstpointer a,
    gconstpointer b)
{
	lang_info_t *t1 = (lang_info_t *)a;
	lang_info_t *t2 = (lang_info_t *)b;
	gint ret = 0;

	ret = g_utf8_collate(t1->lang_name, t2->lang_name);

	return (ret);
}

gint
orchestrator_om_get_install_languages(
    GList **languages,
    gint *total)
{
	gint ret = OM_SUCCESS;
	lang_info_t *info;

	g_assert(languages != NULL);
	g_assert(total != NULL);

	info = om_get_install_lang_info(total);
	*languages = NULL;
	while (info) {
		*languages = g_list_append(*languages, info);
		info = info->next;
	}
	*languages = g_list_sort(*languages, language_cmp);

	return (ret);
}

gint
orchestrator_om_get_available_languages(GList **languages, gint *total)
{
	gint ret = OM_SUCCESS;
	lang_info_t *info;

	g_assert(languages != NULL);
	g_assert(total != NULL);

	info = om_get_lang_info(total);
	*languages = NULL;
	while (info) {
		*languages = g_list_append(*languages, info);
		info = info->next;
	}
	*languages = g_list_sort(*languages, language_cmp);
	/*
	 * Add C/Posix to the language list
	 */
	if (nodefault.lang_name == NULL)
		nodefault.lang_name = g_strdup(_(NODEFAULTLANGLABEL));
	if (nodefault.lang == NULL)
		nodefault.lang = g_strdup(_(NODEFAULTLANGLABEL));
	*languages = g_list_prepend(*languages, &nodefault);
	(*total)++;

	return (ret);
}

gchar *
orchestrator_om_language_get_name(lang_info_t *language)
{
	if (!language)
		return (NULL);
	else if (language->lang_name)
		return (language->lang_name);
	else if (language->lang)
		return (language->lang);
	else /* This should not happen */
		return (_("Unknown Language"));
}

gchar *
orchestrator_om_language_get_code(lang_info_t *language)
{
	if (!language)
		return (NULL);
	else
		return (language->lang);
}

void
orchestrator_om_free_language(lang_info_t *language)
{
	om_free_lang_info(language);
}

locale_info_t *
orchestrator_om_language_get_locales(lang_info_t *language)
{
	if (!language)
		return (NULL);
	else
		return (language->locale_info);
}

gint
orchestrator_om_language_get_locale_count(lang_info_t *language)
{
	if (!language)
		return (NULL);
	else
		return (language->n_locales);
}

gboolean
orchestrator_om_language_is_default(lang_info_t *language)
{
	if (!language || !language->def_lang)
		return (FALSE);
	else
		return (TRUE);
}

gchar *
orchestrator_om_locale_get_name(locale_info_t *locale)
{
	if (!locale)
		return (NULL);
	else
		return (locale->locale_name);
}

gchar *
orchestrator_om_locale_get_desc(locale_info_t *locale)
{
	if (!locale)
		return (NULL);
	else
		return (locale->locale_desc);
}

gboolean
orchestrator_om_locale_is_default(locale_info_t *locale)
{
	if (!locale || !locale->def_locale)
		return (FALSE);
	else
		return (TRUE);
}

locale_info_t *
orchestrator_om_locale_get_cposix(void)
{
	return (&cposix);
}

gboolean
orchestrator_om_locale_is_cposix(locale_info_t *locale)
{
	return (locale == &cposix);
}

gboolean
orchestrator_om_locale_is_utf8(locale_info_t *locale)
{
	gchar *str = NULL;

	str = g_strstr_len(locale->locale_name,
	    strlen(locale->locale_name), "UTF-8");
	return (str != NULL);
}

void
orchestrator_om_free_locale(locale_info_t *locale)
{
	om_free_locale_info(locale);
}

void
orchestrator_om_set_install_lang_by_value(lang_info_t *locale_info)
{
	om_set_install_lang_by_value(locale_info);
}

void
orchestrator_om_set_install_lang_by_name(char *lang_name)
{
	om_set_install_lang_by_name(lang_name);
}

int
orchestrator_om_perform_install(
    nvlist_t *uchoices,
    om_callback_t callback)
{
	return (om_perform_install(uchoices, callback));
}
