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
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _ORCHESTRATOR_LANG_CODES_H
#define	_ORCHESTRATOR_LANG_CODES_H

#pragma ident	"@(#)orchestrator_lang_codes.h	1.2	07/08/25 SMI"

/*
 * This list is created from the ISO 639-1 language code list. It does
 * Not include codes for ISO 639-2 or 3 codes.
 */

#ifdef	__cplusplus
extern "C" {
#endif


struct orchestrator_langs {
	char 	*lang_code;
	char	*lang_name;
} orchestrator_lang_list[] = {
	{"aa", "Afar"},
	{"ab", "Abkhazian"},
	{"af", "Afrikaans"},
	{"am", "Amharic"},
	{"ar", "Arabic"},
	{"as", "Assamese"},
	{"ay", "Aymara"},
	{"az", "Azerbaijani"},
	{"ba", "Bashkir"},
	{"be", "Byelorussian"},
	{"bg", "Bulgarian"},
	{"bh", "Bihari"},
	{"bi", "Bislama"},
	{"bn", "Bengali"},
	{"bo", "Tibetan"},
	{"br", "Breton"},
	{"ca", "Catalan"},
	{"co", "Corsican"},
	{"cs", "Czech"},
	{"cy", "Welsh"},
	{"da", "Danish"},
	{"de", "German"},
	{"dz", "Bhutani"},
	{"el", "Greek"},
	{"en", "English"},
	{"eo", "Esperanto"},
	{"es", "Spanish"},
	{"et", "Estonian"},
	{"eu", "Basque"},
	{"fa", "Persian"},
	{"fi", "Finnish"},
	{"fj", "Fiji"},
	{"fo", "Faeroese"},
	{"fr", "French"},
	{"fy", "Frisian"},
	{"ga", "Irish"},
	{"gd", "Gaelic"},
	{"gl", "Galician"},
	{"gn", "Guarani"},
	{"gu", "Gujarati"},
	{"ha", "Hausa"},
	{"hi", "Hindi"},
	{"he", "Hebrew"},
	{"hr", "Croatian"},
	{"hu", "Hungarian"},
	{"hy", "Armenian"},
	{"ia", "Interlingua"},
	{"ie", "Interlingue"},
	{"ik", "Inupiak"},
	{"in", "Indonesian"},
	{"is", "Icelandic"},
	{"it", "Italian"},
	{"iw", "Hebrew"},
	{"ja", "Japanese"},
	{"ji", "Yiddish"},
	{"jw", "Javanese"},
	{"ka", "Georgian"},
	{"kk", "Kazakh"},
	{"kl", "Greenlandic"},
	{"km", "Cambodian"},
	{"kn", "Kannada"},
	{"ko", "Korean"},
	{"ks", "Kashmiri"},
	{"ku", "Kurdish"},
	{"ky", "Kirghiz"},
	{"la", "Latin"},
	{"ln", "Lingala"},
	{"lo", "Laothian"},
	{"lt", "Lithuanian"},
	{"lv", "Latvian"},
	{"mg", "Malagasy"},
	{"mi", "Maori"},
	{"mk", "Macedonian"},
	{"ml", "Malayalam"},
	{"mn", "Mongolian"},
	{"mo", "Moldavian"},
	{"mr", "Marathi"},
	{"ms", "Malay"},
	{"mt", "Maltese"},
	{"my", "Burmese"},
	{"na", "Nauru"},
	{"nb", "Norwegian Bokmal"},
	{"ne", "Nepali"},
	{"nl", "Dutch"},
	{"nn", "Norwegian Nynorsk"},
	{"no", "Norwegian"},
	{"oc", "Occitan"},
	{"om", "Oromo"},
	{"or", "Oriya"},
	{"pa", "Punjabi"},
	{"pl", "Polish"},
	{"ps", "Pashto"},
	{"pt", "Portuguese"},
	{"qu", "Quechua"},
	{"rm", "Rhaeto-Romance"},
	{"rn", "Kirundi"},
	{"ro", "Romanian"},
	{"ru", "Russian"},
	{"rw", "Kinyarwanda"},
	{"sa", "Sanskrit"},
	{"sd", "Sindhi"},
	{"sg", "Sangro"},
	{"sh", "Serbo-Croatian"},
	{"si", "Singhalese"},
	{"sk", "Slovak"},
	{"sl", "Slovenian"},
	{"sm", "Samoan"},
	{"sn", "Shona"},
	{"so", "Somali"},
	{"sq", "Albanian"},
	{"sr", "Serbian"},
	{"ss", "Siswati"},
	{"st", "Sesotho"},
	{"su", "Sudanese"},
	{"sv", "Swedish"},
	{"sw", "Swahili"},
	{"ta", "Tamil"},
	{"te", "Tegulu"},
	{"tg", "Tajik"},
	{"th", "Thai"},
	{"ti", "Tigrinya"},
	{"tk", "Turkmen"},
	{"tl", "Tagalog"},
	{"tn", "Setswana"},
	{"to", "Tonga"},
	{"tr", "Turkish"},
	{"ts", "Tsonga"},
	{"tt", "Tatar"},
	{"tw", "Twi"},
	{"uk", "Ukrainian"},
	{"ur", "Urdu"},
	{"uz", "Uzbek"},
	{"vi", "Vietnamese"},
	{"vo", "Volapuk"},
	{"wo", "Wolof"},
	{"xh", "Xhosa"},
	{"yo", "Yoruba"},
	{"zh", "Chinese"},
	{"zu", "Zulu"},
	/* C locale expansion is added per local */
	/* conventions though not a part of iso639 standard */
	{"C", "English"}
};

struct orchestrator_countries {
	char 	*country_code;
	char	*country_name;
} orchestrator_country_list[] = {
	{"AL", "Albania"},
	{"AR", "Argentina"},
	{"AT", "Austria"},
	{"AU", "Australia"},
	{"BA", "Bosnia and Herzegovina"},
	{"BE", "Belgium"},
	{"BO", "Bolivia"},
	{"BG", "Bulgaria"},
	{"BR", "Brazil"},
	{"CA", "Canada"},
	{"CH", "Switzerland"},
	{"CL", "Chile"},
	{"CO", "Colombia"},
	{"CR", "Costa Rica"},
	{"CS", "Serbia and Montenegro"},
	{"CY", "Cyprus"},
	{"CN", "China"},
	{"CZ", "Czech Republic"},
	{"DE", "Germany"},
	{"DK", "Denmark"},
	{"EC", "Ecuador"},
	{"EE", "Estonia"},
	{"EG", "Egypt"},
	{"ES", "Spain"},
	{"FI", "Finland"},
	{"FR", "France"},
	{"GB", "Great Britain"},
	{"GR", "Greece"},
	{"GT", "Guatemala"},
	{"HR", "Croatia"},
	{"HK", "Hong Kong"},
	{"HU", "Hungary"},
	{"IE", "Ireland"},
	{"IL", "Israel"},
	{"IN", "India"},
	{"IS", "Iceland"},
	{"IT", "Italy"},
	{"JP", "Japan"},
	{"KO", "Korea"},
	{"LT", "Lithuania"},
	{"LU", "Luxembourg"},
	{"LV", "Latvia"},
	{"MK", "Macedonia"},
	{"MT", "Malta"},
	{"MX", "Mexico"},
	{"NO", "Norway"},
	{"NI", "Nicaragua"},
	{"NL", "Netherlands"},
	{"NZ", "New Zealand"},
	{"PA", "Panama"},
	{"PE", "Peru"},
	{"PL", "Poland"},
	{"PT", "Portugal"},
	{"PY", "Paraguay"},
	{"RO", "Romania"},
	{"RU", "Russia"},
	{"SA", "Saudi Arabia"},
	{"SE", "Sweden"},
	{"SI", "Slovenia"},
	{"SK", "Slovakia"},
	{"SV", "El Salvador"},
	{"TH", "Thailand"},
	{"TR", "Turkey"},
	{"TW", "Taiwan"},
	{"US", "United States"},
	{"UY", "Uruguay"},
	{"VE", "Venezuela"},
	{"ZH", "China"}
};
#ifdef	__cplusplus
}
#endif

#endif	/* _ORCHESTRATOR_LANG_CODES_H */
