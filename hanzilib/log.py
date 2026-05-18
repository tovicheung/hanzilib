# This file is part of hanzilib, a fork of cjklib.
#
# hanzilib is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# hanzilib is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with hanzilib.  If not, see <http://www.gnu.org/licenses/>.


# Simple logging

import sys

# config
enabled = True
file = sys.stderr
_indent = 0

def indent():
    global _indent
    _indent += 2

def dedent():
    global _indent
    _indent -= 2

def task(string):
    if enabled:
        print(" " * _indent + "\033[1;36m" + str(string) + "\033[m", file=file)
        indent()

def log(string):
    if enabled:
        print(" " * _indent + "\033[m" + str(string) + "\033[m", file=file)

def list(l):
    if enabled:
        indent()
        for item in l:
            print(" " * _indent + str(item), file=file)
        dedent()

def success(string):
    if enabled:
        print(" " * _indent + "\033[1;32m" + str(string) + "\033[m", file=file)

def warn(string):
    if enabled:
        print(" " * _indent + "\033[1;33m" + str(string) + "\033[m", file=file)

def error(string):
    if enabled:
        print(" " * _indent + "\033[1;31m" + str(string) + "\033[m", file=file)
