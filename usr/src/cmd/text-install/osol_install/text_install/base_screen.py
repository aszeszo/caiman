#
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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

'''
Common screen functionality for text installer UI
'''

from osol_install.text_install import _

class QuitException(StandardError):
    '''Raised when a function needs to force the program to quit gracefully'''
    pass


class RebootException(SystemExit):
    '''Raised when user requests reboot'''
    pass


class SkipException(StandardError):
    '''Raised to signal this screen should be skipped'''
    pass


class UIMessage(StandardError):
    '''Exception class for passing an error message to the UI'''
    
    def get_message(self):
        if self.args and self.args[0]:
            return self.args[0]
        else:
            return ""
    
    message = property(get_message)


class BaseScreen(object):
    '''Abstract base class for screens, providing some common
    functionality for all screens.
    
    HEADER_TEXT: Default header text for this screen. Screens which have
    permanent, static headers can define this variable at the class level.
    Dynamically titled screens should set the default here, and override
    self.header_text at the instance level as needed.
    
    '''
    
    HEADER_TEXT = "DEFAULT TEXT"
    CONFIRM_QUIT_HEADER = _("Confirm: Quit the Installer?")
    QUIT_TEXT = _("Do you want to quit the Installer?")
    QUIT_DISK_MOD_TEXT = _("Do you want to quit the Installer?\n\n"
                           "Any changes made to the disk by the "
                           "Installer will be left \"as is.\"")
    CANCEL_BUTTON = _("Cancel")
    CONFIRM_BUTTON = _("Quit")
    
    def __init__(self, main_win):
        '''Set main_win and store win_size_y and win_size_x'''
        self.instance = ""
        self.main_win = main_win
        self.center_win = self.main_win.central_area
        self._win_size = self.center_win.window.getmaxyx()
        self.header_text = self.HEADER_TEXT
        self.install_profile = None
        self.orig_border = (0, 0)
    
    def get_win_size_y(self):
        '''Return the window size, adjusted based on the specified border'''
        return self._win_size[0] - self.center_win.border_size[0] * 2
    
    def get_win_size_x(self):
        '''Return the window size, adjusted based on the specified border'''
        return self._win_size[1] - self.center_win.border_size[1] * 2
    
    win_size_x = property(get_win_size_x)
    win_size_y = property(get_win_size_y)
    
    def set_actions(self):
        '''Subclasses of BaseScreen should override this function to
        add/remove Actions from their attached main_win object
        
        '''
        pass
    
    def show(self, install_profile):
        '''Wrapper method for common entry/exit functionality into _show.
        This method performs the common tasks of clearing the main_win of
        the previous screen's objects, resetting and setting the actions,
        and setting the header_text.
        
        This method then call's _show, which should be overridden by the
        subclass.
        
        '''
        self.install_profile = install_profile
        self.orig_border = self.center_win.border_size
        try:
            self.main_win.clear()
            self.set_actions()
            self.main_win.show_actions()
            self.main_win.set_header_text(self.header_text)
            
            self._show()
            self.main_win.do_update()
            return self.validate_loop()
        except QuitException:
            return None
        except SkipException:
            return self.main_win.screen_list.get_next(self, skipped=True)
        finally:
            self.center_win.border_size = self.orig_border
    
    def _show(self):
        '''Abstract base method. Subclasses should override this method to
        set-up any lists, editable fields, or text relevant to this screen
        
        '''
        raise NotImplementedError, "Subclasses must override the 'show' method"
    
    def validate_loop(self):
        '''
        Validation loop. Runs main_win.process_input to accept user input
        while the screen is active. When the user tries to move to another
        screen, validate (if moving onward), save state by calling
        on_change_screen and either on_prev or on_continue.
        '''
        continue_validate = True
        while continue_validate:
            next_screen = self.main_win.process_input(self)
            if (self.main_win.screen_list.peek_last() == self and
                next_screen != self.main_win.screen_list.help):
                try:
                    self.validate()
                    continue_validate = False
                    self.on_continue()
                except UIMessage as msg:
                    self.main_win.screen_list.previous_screen()
                    error_str = unicode(msg)
                    if error_str:
                        self.main_win.error_line.display_err(error_str)
            elif next_screen is None:
                if self.confirm_quit():
                    raise QuitException
            else:
                continue_validate = False
                self.on_prev()
        self.on_change_screen()
        self.center_win.make_inactive()
        return next_screen
    
    def confirm_quit(self):
        '''Confirm the user truly wants to quit. Can be overridden by
        sub-classes needing to do any clean-up, such as signaling other
        threads to shutdown.
        
        '''
        return self.main_win.pop_up(BaseScreen.CONFIRM_QUIT_HEADER,
                                    BaseScreen.QUIT_TEXT,
                                    BaseScreen.CANCEL_BUTTON,
                                    BaseScreen.CONFIRM_BUTTON)
    
    def validate(self):
        '''
        This function is called whenever the user tries to continue forward.
        Screens should override this function to do any final checks for data
        validity. If any problems are found, a UIMessage should be raised,
        with a string indicating the issue. The string will be displayed to the
        screen (and must be 78 characters or less)
        '''
        pass
    
    def on_prev(self):
        '''
        Called prior to leaving this screen, but only if quitting or moving to
        the prior screen. This function should be overridden if data needs to
        be preserved differently if the user is going 'back' instead of
        'forward'
        '''
        pass
    
    def on_continue(self):
        '''
        Called prior to leaving this screen, but only if moving to the next
        screen. This function should be overridden if data needs to be
        preserved differently if the user is going 'forward' instead of 'back'
        '''
        pass
    
    def on_change_screen(self):
        '''
        Called prior to leaving this screen, regardless of direction. Most data
        preservation should be done here, unless the data needs to be handled
        differently depending on the direction the user is going.
        '''
        pass
