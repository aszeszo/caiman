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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <math.h>
#include <glib/gi18n.h>
#include "string.h"

#include "orchestrator-wrappers.h"

static float
round_up_to_tenths(float value)
{
        float newval;

        newval = roundf((value)*10.0) / 10.0;
        if(newval < value)
                newval += 0.1;
        return newval;
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

	for (i = 0; i < FD_NUMPART; i++) {
		partition = &partitions->pinfo[i];
		if (orchestrator_om_get_partition_type(partition) ==
		    partitiontype) {
			if (partitiontype != SUNIXOS)
				numfound++;
			/* Could also be linux swap so need to check content type */
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
orchestrator_om_get_num_partitions(disk_parts_t *partitions)
{
	partition_info_t *partition = NULL;
	gint numfound = 0;

	g_return_val_if_fail(partitions != NULL, -1);
	for (gint i = 0; i < FD_NUMPART; i++) {
		partition = &partitions->pinfo[i];
		if ((partition->partition_id > 0) &&
		    (partition->partition_id <= FD_NUMPART))
			numfound++;
	}
	return (numfound);
}

partition_info_t *
orchestrator_om_get_part_by_blkorder(
    disk_parts_t *partitions,
    guint order)
{
	gint i;
	gint numparts = 0;

	g_return_val_if_fail(partitions != NULL, NULL);
	g_return_val_if_fail(((order >= (guint)0) && (order < FD_NUMPART)), NULL);
	numparts = orchestrator_om_get_num_partitions(partitions);
	if (order >= numparts)
		return (NULL);

	for (i = 0; i < FD_NUMPART; i++) {
		if (partitions->pinfo[i].partition_order == order+1)
			return (&partitions->pinfo[i]);
	}
	return (NULL);
}

/* Find the first available partition and initialise it */
partition_info_t *
orchestrator_om_find_unused_partition(
    disk_parts_t *partitions,
    guint partitiontype,
    gint order)
{
	partition_info_t *partition = NULL;
	gint highest = 0;

	g_return_val_if_fail(partitions != NULL, NULL);
	g_return_val_if_fail((order >= 0) && (order < FD_NUMPART), NULL);

	/*
	 * Find the lowest numbered partition ID that's not in use by
	 * an existing partition
	 */
	for (gint i = 0; i < FD_NUMPART; i++) {
		partition = &partitions->pinfo[i];
		if (partition->partition_id > highest)
			highest = partition->partition_id;
	}

	if (highest >= FD_NUMPART) {
		g_warning("Device %s already has all %d primary partitions in use",
		    partitions->disk_name, FD_NUMPART);
	}

	/* Find the first available slot in the pinfo array */
	for (gint i = 0; i <  FD_NUMPART; i++) {
		partition = &partitions->pinfo[i];
		/*
		 * FIXME: Shouldn't have to check for partition_type == 0
		 */
		if ((partition->partition_type == UNUSED ||
				partition->partition_type == 0) &&
			partition->partition_order < 1) {
			partition->partition_type = partitiontype;
			partition->partition_order = order+1;
			partition->partition_id = highest+1;
			return (partition);
		}
	}
	return (NULL);
}

guint
orchestrator_om_get_partition_type(partition_info_t *partition)
{
	/* FIXME - what's the difference between content type and partition type?? */
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

void
orchestrator_om_set_partition_sizegb(
    partition_info_t *partition,
    gfloat size)
{
	/* convert GB to MB (1024MB = 1GB) */
	gdouble newsize = 0;
	g_return_if_fail(size >= 0);
	newsize = size * MBPERGB;
	if (partition)
		partition->partition_size = (uint64_t)newsize;
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

gfloat
orchestrator_om_get_disk_sizegb(disk_info_t *dinfo)
{
	g_return_val_if_fail(dinfo != NULL, (gfloat)-1);
	return ((gfloat)(dinfo->disk_size)/MBPERGB);
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
	return ((guint64)om_get_recommended_size(NULL, NULL)/MBPERGB);
}

gint
orchestrator_om_get_upgrade_targets_by_disk(
    disk_info_t *dinfo,
    upgrade_info_t **uinfo,
    guint16 *found)
{
	*uinfo = om_get_upgrade_targets_by_disk(omhandle, dinfo->disk_name, found);
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
		return (g_strdup_printf(_("%ss%d"), uinfo->instance.uinfo.disk_name,
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

/* keyboard layout stuff */
static gint
keyboard_cmp(
    gconstpointer a,
    gconstpointer b)
{
	keyboard_type_t *t1 = (keyboard_type_t *)a;
	keyboard_type_t *t2 = (keyboard_type_t *)b;
	gint ret = 0;

	ret = g_utf8_collate(t1->kbd_name, t2->kbd_name);

	return (ret);
}

gint
orchestrator_om_get_keyboard_type(
    GList **keyboard,
    gint *total)
{
	gint ret = OM_SUCCESS;
	keyboard_type_t *types;

	g_assert(keyboard != NULL);
	g_assert(total != NULL);
	types = om_get_keyboard_types(total);
	*keyboard = NULL;
	while (types) {
		*keyboard = g_list_append(*keyboard, types);
		types = types->next;
	}
	*keyboard = g_list_sort(*keyboard, keyboard_cmp);

	return (ret);
}

gint
orchestrator_om_set_keyboard_type(keyboard_type_t *keyboard)
{
	gint ret = 0;

	ret = om_set_keyboard_by_num(keyboard->kbd_num);

	return (ret);
}

gboolean
orchestrator_om_keyboard_is_self_id(void)
{
	boolean_t ret = B_FALSE;
	ret = om_is_self_id_keyboard();

	if (ret == B_FALSE)
		return (FALSE);
	else
		return (TRUE);
}

gchar *
orchestrator_om_keyboard_get_name(keyboard_type_t *keyboard)
{
	if (keyboard)
		return (keyboard->kbd_name);
	else
		return (NULL);
}

gint
orchestrator_om_keyboard_get_num(keyboard_type_t *keyboard)
{
	if (keyboard)
		return (keyboard->kbd_num);
	else
		return (-1);
}

/* language stuff */
static locale_info_t cposix = {
	N_("C/Posix"),
	N_("C/Posix"),
	B_FALSE,
	NULL
};

static lang_info_t nodefault = {
	&cposix,
	B_FALSE,
	N_("No default language support"),
	1,
	N_("No default language support"),
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

void
orchestrator_om_set_preinstal_time_zone(
    gchar *country,
    gchar *timezone)
{
	om_set_preinstall_timezone(country, timezone);
}

int
orchestrator_om_perform_install(
    nvlist_t *uchoices,
    om_callback_t callback)
{
	return (om_perform_install(uchoices, callback));
}

