#######################################################################################################################
# HDL_Syntax - Verilog and SystemVerilog syntax with Sublime Text 4                                                   #
# Copyright (C) 2021  Dawid Szulc                                                                                     #
#                                                                                                                     #
# This program is free software: you can redistribute it and/or modify                                                #
# it under the terms of the GNU General Public License as published by                                                #
# the Free Software Foundation, either version 3 of the License, or                                                   #
# (at your option) any later version.                                                                                 #
#                                                                                                                     #
# This program is distributed in the hope that it will be useful,                                                     #
# but WITHOUT ANY WARRANTY; without even the implied warranty of                                                      #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the                                                       #
# GNU General Public License for more details.                                                                        #
#                                                                                                                     #
# You should have received a copy of the GNU General Public License                                                   #
# along with this program.  If not, see <https://www.gnu.org/licenses/>.                                              #
#######################################################################################################################

import datetime
import os
import re
import sublime
import sublime_plugin

class SublimeModified(sublime_plugin.EventListener):

    def on_modified_async(self, view):
        '''Called after changes have been made to the view. Runs in a separate thread, and does not block the
        application.

        :param view: Represents a view into a text buffer
        :type view: sublime.View
        '''
        # Update current status
        HDL_Preprocessor.modified_time = datetime.datetime.now().timestamp()
        HDL_Preprocessor.modified_view = view
        # Get settings
        settings.reload(view)
        delay = settings.delay()
        # Track modifications
        sublime.set_timeout_async(HDL_Preprocessor.track_modifications, 1050 * delay)

class HDL_Preprocessor:
    '''Verilog and SystemVerilog preprocessor with Sublime Text 4
    '''

    def __init__(self):
        '''Initialization
        '''
        self.modified_time = datetime.datetime.now().timestamp()  # Time of last modification
        self.compiled_time = datetime.datetime.now().timestamp()  # Time of last compilation
        self.modified_view = None  # Last modified view

    def get_os_path(self, view):
        '''Returns some useful data on pathnames

        :param view: Represents a view into a text buffer
        :type view: sublime.View
        :return (Everything leading up to last pathname component, Last pathname component, Extension)
        :rtype: (str, str, str)
        '''
        head, tail, ext = ('', '', '')
        file_name = view.file_name()
        if file_name is not None:
            ext = os.path.splitext(file_name)[1].lower()
            head, tail = os.path.split(file_name)
        return head, tail, ext

    def track_modifications(self):
        '''Check if the content of the file has changed
        '''
        if self.modified_time > self.compiled_time:
            now = datetime.datetime.now().timestamp()
            view = self.modified_view
            # Get settings
            delay = settings.delay()
            # Check changes
            if (now - self.modified_time) > 0.95 * delay:
                self.compiled_time = self.modified_time
                if type(view) == sublime.View:
                    head, tail, ext = self.get_os_path(view)
                    self.head = [head]
                    if ext in ['.v', '.vh', '.sv', '.svh']:
                        # Get file content
                        sublime_region = sublime.Region(0, view.size())
                        content = view.substr(sublime_region)
                        self.defines = []
                        self.conditionals = []
                        regions = self.preproc(content)
                        view.erase_regions('HDL_Preprocesor')
                        view.add_regions(
                            'HDL_Preprocesor', regions, 'comment', '', sublime.DRAW_EMPTY
                        )

    def preproc(self, content):
        '''Preprocessor file content

        :param content: File content
        :type content: str
        :return regions
        :rtype: list of regions
        '''
        # Get settings
        incdirs = settings.incdirs()
        # Initialize preprocessor
        pos = 0
        match = True
        exclude = False
        exclude_pos_start = 0
        exclude_pos_end = 0
        regions = []
        # Search preprocessor directives
        while pos < len(content):
            pattern = re.compile(r'(`|"|\/\/|\/\*)')
            match = pattern.search(content, pos)
            if match:
                match_start = match.start(1)
                match_end = match.end(1)
                match_x = match.group(1)
                # Single line comment
                if match_x == '//':
                    pattern = re.compile(r'(\n)')
                    match = pattern.search(content, match_end)
                    if match:
                        pos = match.end(1)
                    else:
                        pos = len(content)
                        print('HDL_Syntax: Signle line comment is not ended with `newline`.')
                # Multi line comment
                elif match_x == '/*':
                    pattern = re.compile(r'(\*\/)')
                    match = pattern.search(content, match_end)
                    if match:
                        pos = match.end(1)
                    else:
                        pos = len(content)
                        print('HDL_Syntax: Multi line comment is not ended with `*/`.')
                # String
                elif match_x == '"':
                    pattern = re.compile(r'(?<!\\)(")')
                    match = pattern.search(content, match_end)
                    if match:
                        pos = match.end(1)
                    else:
                        pos = len(content)
                        print('HDL_Syntax: String is not ended with `"`.')
                # Preprocessor directive
                elif match_x == '`':
                    match = False
                    # Include
                    if not match:
                        pattern = re.compile(r'(`include) "([^"]+)"')
                        match = pattern.match(content, match_start)
                        if match:
                            file_name = os.path.join(self.head[-1], match.group(2))
                            file_name = os.path.normpath(file_name)
                            if os.path.isfile(file_name):
                                try:
                                    with open(file_name, 'r') as file:
                                        self.head.append(os.path.split(file_name)[0])
                                        include_content = file.read()
                                        self.preproc(include_content)
                                        del self.head[-1]
                                except OSError:
                                    print(f"HDL_Syntax: Can\'t open `{file_name}` file.")
                            else:
                                for incdir in incdirs:
                                    file_name = os.path.join(incdir, match.group(2))
                                    file_name = os.path.normpath(file_name)
                                    if os.path.isfile(file_name):
                                        try:
                                            with open(file_name, 'r') as file:
                                                self.head.append(os.path.split(file_name)[0])
                                                include_content = file.read()
                                                self.preproc(include_content)
                                                del self.head[-1]
                                        except OSError:
                                            print(f"HDL_Syntax: Can\'t open `{file_name}` file.")
                                        break
                            pos = match.end(2) + 1
                    # Define
                    if not match:
                        pattern = re.compile(r'(`define) ([a-zA-Z_][a-zA-Z0-9_$]*)')
                        match = pattern.match(content, match_start)
                        if match:
                            if match.group(2) not in self.defines:
                                self.defines.append(match.group(2))
                                pos = match.end(2)
                    # Undefine
                    if not match:
                        pattern = re.compile(r'(`undef)\s+([a-zA-Z_][a-zA-Z0-9_$]*)')
                        match = pattern.match(content, match_start)
                        if match:
                            if match.group(2) in self.defines:
                                self.defines.remove(match.group(2))
                                pos = match.end(2)
                    # Reset all defines
                    if not match:
                        pattern = re.compile(r'(`resetall)[^a-zA-Z0-9_$]')
                        match = pattern.match(content, match_start)
                        if match:
                            self.defines = []
                            pos = match.end(1)
                    # Preprocessor if
                    if not match:
                        pattern = re.compile(r'(`ifdef)\s+([a-zA-Z_][a-zA-Z0-9_$]*)')
                        match = pattern.match(content, match_start)
                        if match:
                            self.conditionals.append({
                                'equal': True if match.group(2) in self.defines else False,
                                'exclude': True if not exclude and match.group(2) not in self.defines else False,
                            })
                            if not exclude and match.group(2) not in self.defines:
                                exclude = True
                                exclude_pos_start = match.start(1)
                            pos = match.end(2)
                    # Preprocessor else
                    if not match:
                        pattern = re.compile(r'(`else)[^a-zA-Z0-9_$]')
                        match = pattern.match(content, match_start)
                        if match:
                            if not exclude:
                                self.conditionals[-1]['equal'] = True
                                self.conditionals[-1]['exclude'] = True
                                exclude = True
                                exclude_pos_start = match.end(1)
                            elif exclude and self.conditionals[-1]['exclude']:
                                self.conditionals[-1]['equal'] = not self.conditionals[-1]['equal']
                                self.conditionals[-1]['exclude'] = False
                                exclude = False
                                exclude_pos_end = match.start(1)
                                regions.append(sublime.Region(exclude_pos_start, exclude_pos_end))
                            pos = match.end(1)
                    # Preprocessor end
                    if not match:
                        pattern = re.compile(r'(`endif)[^a-zA-Z0-9_$]')
                        match = pattern.match(content, match_start)
                        if match:
                            if exclude and self.conditionals[-1]['exclude']:
                                exclude = False
                                exclude_pos_end = match.end(1)
                                regions.append(sublime.Region(exclude_pos_start, exclude_pos_end))
                            del self.conditionals[-1]
                            pos = match.end(1)
                    # Preprocessor if not
                    if not match:
                        pattern = re.compile(r'(`ifndef)\s+([a-zA-Z_][a-zA-Z0-9_$]*)')
                        match = pattern.match(content, match_start)
                        if match:
                            self.conditionals.append({
                                'equal': True if match.group(2) not in self.defines else False,
                                'exclude': True if not exclude and match.group(2) in self.defines else False,
                            })
                            if not exclude and match.group(2) in self.defines:
                                exclude = True
                                exclude_pos_start = match.start(1)
                            pos = match.end(2)
                    if not match:
                        pos = match_end
                else:
                    pos = match_end
            else:
                pos = len(content)
        return regions


class HDL_Preprocessor_settings:
    '''Handle HDL_Preprocessor settings
    '''

    def __init__(self):
        '''Settings initialization
        '''
        self.settings = {}

    def reload(self, view):
        '''Reload settings from file
        '''
        # Reload user settings
        self.settings = sublime.load_settings('HDL_Syntax.sublime-settings')
        self.settings = self.settings.to_dict()
        # Reload project settings
        project_data = view.window().project_data()
        if project_data is not None and type(project_data) == dict:
            settings = project_data.get('settings')
            if settings is not None and type(settings) == dict:
                for key, value in settings.items():
                    if key.startswith('HDL_Syntax_') or key == 'HDL_Linter_incdirs':
                        key = key[11:]
                        if type(self.settings.get(key)) == list:
                            self.settings[key] += value
                        else:
                            self.settings[key] = value

    def delay(self):
        '''Minimum delay in seconds before linter run
        '''
        # Get setting
        setting = self.settings.get('delay')
        # Possible values: int, float
        if type(setting) == float or type(setting) == int:
            return setting
        # Default value: 0.1
        setting = 0.1
        print(f"HDL_Syntax: `delay` changed to default value `{setting}`")
        return setting

    def incdirs(self):
        '''Specify directories to be searched for files included using Verilog `include
        '''
        # Get setting
        setting = self.settings.get('incdirs')
        # Possible values: list of "<path>"
        if type(setting) == list:
            copy = setting[:]
            for path in reversed(copy):
                if type(path) != str or not os.path.isdir(path):
                    print(f"HDL_Syntax: path `{path}` removed from `incdirs`")
                    setting.remove(path)
            return setting
        # Default value: []
        setting = []
        print(f"HDL_Syntax: `incdirs` changed to default value `[]`")
        return setting


settings = HDL_Preprocessor_settings()
HDL_Preprocessor = HDL_Preprocessor()
