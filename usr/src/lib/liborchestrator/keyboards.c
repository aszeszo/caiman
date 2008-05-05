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


#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#include <stropts.h>
#include <sys/kbio.h>
#include <libintl.h>
#include <locale.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/int_types.h>

#include "orchestrator_private.h"

#define	debug	1

keyboard_type_t	*keyboard_listp = NULL;

static int16_t add_keyboard_record(char *buf, char *result);
static int get_layouts(int *total);
static int set_keyboard_common(kbd_data_t type, uintptr_t arg);
static int store_layout(char *kbd);
static int wrt_kbdfile(char *kbd);

/*
 * om_is_self_id_keyboard
 * This function indicates whether the keyboard found is self identifying
 * in terms of character set.
 * Input:	None
 * Output:	None
 * Return:	true, if self identifying
 *		false, if not self identifying
 */

boolean_t
om_is_self_id_keyboard(void)
{
	/*
	 * For Dwarf the keyboard settings do not take affect appropriately
	 * due to missing X event handling. Thus we must return
	 * TRUE for is self identifying and allow the original sysidkbd
	 * mechanism to handle the keyboard setting before X is started.
	 */

	return (B_TRUE);
}

/*
 * om_get_keyboard_types
 * This function returns a list of keyboard types that are supported
 * with Solaris
 * Input:	None
 * Output:	None
 * Return:	Pointer to keyboard_type_t structure which is a linked
 *		list of supported keyboard types.
 *
 * Error Handling:
 *		If no keyboard types are found, a NULL list is returned
 *		and error is set to OM_FAILURE.
 *
 *		Otherwise error code is set to OM_SUCCESS.
 *
 */
keyboard_type_t *
om_get_keyboard_types(int *total)
{
	int	num;

	/*
	 * If keyboard not self identifying and no previous failure,
	 * return list of supported keyboards.
	 */

	if (get_layouts(&num) != 0) {
		om_debug_print(OM_DBGLVL_WARN,  "kbd: Cannot read keyboard "
		    "layouts\n");
		return (NULL);
	}
	*total = num;
	return (keyboard_listp);

}


/*
 * om_set_keyboard_by_num
 * This function sets the current keyboard layout value by the layout
 * number passed in.
 * Input:	int	num, keyboard layout number to set
 * Output:	None
 * Return:	Failure, if not able to set
 *		Success, if keyboard is set
 */
int
om_set_keyboard_by_num(int num)
{
	return (set_keyboard_common(KBD_NUM, (uintptr_t)&num));
}

/*
 * om_set_keyboard_by_name
 * This function sets the current keyboard layout value by the layout
 * name passed in.
 * Input:	char *name, keyboard layout name to set
 * Output:	None
 * Return:	Failure, if not able to set
 *		Success, if keyboard is set
 */
int
om_set_keyboard_by_name(char *name)
{
	if (name == NULL)
		return (-1);

	return (set_keyboard_common((int)KBD_NAME, (uintptr_t)name));
}

/*
 * om_set_keyboard_by_value
 * This function sets the current keyboard layout value by the keyboard
 * type structure passed in.
 * Input:	keyboard_type_t *kbd, keyboard structure to use as
 *		values to set keyboard layout.
 * Output:	None
 * Return:	Failure, if not able to set
 *		Success, if keyboard is set
 */
int
om_set_keyboard_by_value(keyboard_type_t *kbd)
{

	if (kbd == NULL)
		return (-1);

	return (set_keyboard_common((int)KBD_VALUE, (uintptr_t)kbd));
}

void
om_free_keyboard_types(keyboard_type_t *kbd)
{
	keyboard_type_t	*nextp;

	while (kbd != NULL) {
		nextp = kbd->next;
		free(nextp->kbd_name);
		free(kbd);
		kbd = nextp;
	}
}

/*
 * set_keyboard_common
 * Common keyboard layout setting function.
 * Input:	kbd_data_t  type, type of data with which consumer
 *		wants to set keyboard layout.
 * 		uintptr_t   arg, data used for setting the keyboard layout
 *				converted to appropriate type based on
 *				kbd_data_t type value.
 * Output:	None
 * Return:	Failure, if not able to set
 *		Success, if keyboard is set
 */
static int
set_keyboard_common(kbd_data_t type, uintptr_t arg)
{
	/* LINTED */
	int		result = 0;
	char		command[BUFSIZE];
	int		*kbd_num = 0;
	char		*kbd_name = NULL;
	keyboard_type_t	*kp = NULL;

	if (type == KBD_NUM) {
		kbd_num = (int *)arg;
		kp = keyboard_listp;
		while (kp != NULL) {
			if (kp->kbd_num == *kbd_num) {
				break;
			}
			kp = kp->next;
		}
	} else if (type == KBD_NAME) {
		kbd_name = (char *)arg;
	} else if (type == KBD_VALUE) {
		kp = (keyboard_type_t *)arg;
	}

	if (kp != NULL && kp->kbd_name != NULL) {
		kbd_name = kp->kbd_name;
	}
	if (kp == NULL && kbd_name == NULL) {
		om_set_error(OM_UNKNOWN_KEYBOARD);
		return (OM_FAILURE);
	}

	/*
	 * If English-UK or English_US, remap to correct
	 * system names.
	 */
	if (strcmp(kbd_name, "English-UK") == 0) {
		kbd_name = "UK-English";
	} else if (strcmp(kbd_name, "English-US") == 0) {
		kbd_name = "US-English";
	}
	(void) snprintf(command, BUFSIZE,
	    "/usr/bin/kbd -s %s", kbd_name);

	if (system(command) == 0) {
		(void) system("/usr/bin/loadkeys");
		if (store_layout(kbd_name) == 0)
			return (OM_SUCCESS);
	}
	return (OM_FAILURE);
}

/*
 * Static functions
 */

static int
get_layouts(int *total)
{
	FILE	*kbd_file = NULL;
	char	buffer[MAX_LINE_SIZE];
	char	*result = NULL;
	char	*tmpbuf;
	char	*lasts;
	int	i = 0;
	int16_t	ret = 0;

	if ((kbd_file = fopen(KBD_LAYOUT_FILE, "r")) == NULL) {
		om_debug_print(OM_DBGLVL_ERR, "kbd: open file %s failure:\n",
		    KBD_LAYOUT_FILE);
		om_set_error(OM_NO_KBD_LAYOUT);
		return (OM_FAILURE);
	}

	while ((fgets(buffer, MAX_LINE_SIZE, kbd_file) != NULL) &&
	    (i < MAX_LAYOUT_NUM)) {
		if (buffer[0] == '#')
			continue;
		if ((result = strtok(buffer, "=")) == NULL)
			continue;

		tmpbuf = strdup(result);
		if (tmpbuf == NULL) {
			/*
			 * Free any records we created to this point.
			 */
			(void) fclose(kbd_file);
			om_free_keyboard_types(keyboard_listp);
			om_set_error(OM_NO_SPACE);
			return (OM_FAILURE);
		}
		if ((result = strtok_r(NULL, "\n", &lasts)) == NULL) {
			free(tmpbuf);
			continue;
		}

		ret = add_keyboard_record(tmpbuf, result);
		free(tmpbuf);
		if (ret) {
			/*
			 * Free any records we created to this point.
			 */
			om_free_keyboard_types(keyboard_listp);
			om_set_error(ret);
			(void) fclose(kbd_file);
			return (OM_FAILURE);
		}
		i++;
	}
	(void) fclose(kbd_file);
	*total = i;
	return (OM_SUCCESS);
}

static int16_t
add_keyboard_record(char *buf, char *result)
{
	keyboard_type_t *kp;
	boolean_t	is_default = B_FALSE;

	kp = (keyboard_type_t *)malloc(sizeof (keyboard_type_t));
	if (kp == NULL) {
		return (OM_NO_SPACE);
	}

	if (strstr(buf, "UK-English")) {
		kp->kbd_name = strdup(dgettext(TEXT_DOMAIN, "English-UK"));
	} else if (strstr(buf, "US-English")) {
		kp->kbd_name = strdup(dgettext(TEXT_DOMAIN, "English-US"));
		is_default = B_TRUE;
	} else {
		kp->kbd_name = strdup(dgettext(TEXT_DOMAIN, buf));
	}
	if (kp->kbd_name == NULL) {
		om_set_error(OM_NO_SPACE);
		om_free_keyboard_types(kp);
		return (OM_FAILURE);
	}
	kp->kbd_num = strtol(result, NULL, 0);
	kp->is_default = is_default;
	kp->next = keyboard_listp;
	keyboard_listp = kp;
	return (OM_SUCCESS);
}
static int
store_layout(char *kbd)
{
	int nvram_exist;
	char commLine[MAX_LINE_SIZE];

	nvram_exist = check_eeprom(NVRAM_VAR);
	if (nvram_exist != 0)
		return (wrt_kbdfile(kbd));

	(void) snprintf(commLine, MAX_LINE_SIZE, "eeprom %s=%s",
	    NVRAM_VAR, kbd);
	(void) system(commLine);
}

static int
check_eeprom(char *var)
{
	pid_t pid;
	int fd[2];
	int rn;
	int status = 0;
	int ret = 0;
	static char buf[2048];
	int ret2 = -1;

	if (pipe(fd) < 0) {
		om_debug_print(OM_DBGLVL_ERR, "Fail to create a pipe.");
		return (OM_FAILURE);
	}

	if ((pid = fork()) == (pid_t)-1) {
		om_debug_print(OM_DBGLVL_ERR, "Fail to create a new process.");
		return (OM_FAILURE);
	}

	if (pid == 0) {
		(void) close(1);
		if (dup(fd[1]) < 0) {
			om_set_error(OM_CANT_DUP_DESC);
			return (OM_FAILURE);
		}
		if (execl("/usr/sbin/eeprom", "eeprom", NULL) < 0) {
			om_log_print("Failed to run eeprom program");
			om_set_error(OM_CANT_EXEC);
			return (OM_FAILURE);
		}
	} else {
		if (waitpid(pid, &status, 0) == pid) {
			if (WIFEXITED(status)) {
				if ((ret = WEXITSTATUS(status)) != 0) {
					om_set_error(OM_EEPROM_ERROR);
					return (OM_FAILURE);
				}
			}
		}
	}

	if ((rn = read(fd[0], buf, 2047)) < 0) {
		om_debug_print(OM_DBGLVL_INFO, "No eeprom output.");
		goto done;
	}
	buf[rn] = 0;
	if (strstr(buf, var) == NULL) {
		goto done;
	}
	ret2 = 0;
done:
	(void) close(fd[0]);
	(void) close(fd[1]);
	return (ret2);
}
static int
wrt_kbdfile(char *kbd)
{
	char 	*buf_tmp;
	FILE 	*stream;
	char 	entry_buf[BUFSIZE];
	char 	*filebuf;
	struct 	stat stat_buf;
	char 	buffer[MAX_LINE_SIZE];
	int 	w_size;
	int	len;

	len = strlen(kbd) + 9;

	if (len >= BUFSIZE) {
		len = BUFSIZE;
	}
	snprintf(entry_buf, len, "LAYOUT=%s\n", kbd);
	w_size = strlen(entry_buf);

	if (stat(KBD_DEF_FILE, &stat_buf) == -1) {
		om_debug_print(OM_DBGLVL_WARN, "Can't find default kbd file\n");
		om_set_error(OM_CANT_OPEN_FILE);
		return (OM_FAILURE);
	}

	filebuf = (char *)malloc(stat_buf.st_size + w_size);
	if (filebuf == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}
	(void) memset(filebuf, 0, sizeof (filebuf));

	if ((stream = fopen(KBD_DEF_FILE, "r")) == NULL) {
		om_set_error(OM_CANT_OPEN_FILE);
		free(filebuf);
		return (OM_FAILURE);
	}

	while (fgets(buffer, MAX_LINE_SIZE, stream) != NULL) {
		if (strcmp(buffer, "#LAYOUT=") == 0 ||
		    strcmp(buffer, "LAYOUT=") == 0) {
			(void) strcat(filebuf, entry_buf);
		} else {
			(void) strcat(filebuf, buffer);
		}
	}
	(void) strcat(filebuf, "\n");
	(void) fclose(stream);

	if ((stream = fopen(KBD_DEF_FILE, "w")) == NULL) {
		om_set_error(OM_CANT_OPEN_FILE);
		free(filebuf);
		return (OM_FAILURE);
	}
	w_size = fwrite(filebuf, 1, strlen(filebuf), stream);
	if (w_size < strlen(filebuf)) {
		om_set_error(OM_CANT_WRITE_FILE);
		free(filebuf);
		(void) fclose(stream);
		return (OM_FAILURE);
	}
	(void) fclose(stream);
	free(filebuf);
	return (OM_SUCCESS);
}
