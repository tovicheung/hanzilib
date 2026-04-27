#!/usr/bin/python
# -*- coding: utf-8 -*-
# This file is part of cjklib.
#
# Copyright (C) 2009, 2010 cjklib developers
# Copyright (C) 2009 Raymond Hettinger
#
# cjklib is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# cjklib is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with cjklib.  If not, see <http://www.gnu.org/licenses/>.

"""
Utilities.
"""

import re
import copy
import os.path
import platform
import configparser
from optparse import Option, OptionValueError
import csv
from typing import Callable
import itertools

from sqlalchemy.types import String, Text

# Configuration and file access

def locateProjectFile(relPath, projectName='hanzilib'):
    """
    Locates a project file relative to the project's directory. Returns ``None``
    if module ``pkg_resources`` is not installed or package information is not
    available.

    :type relPath: str
    :param relPath: path relative to project directory
    :type projectName: str
    :param projectName: name of project which will be used as name of the
        config file
    """
    return

def getConfigSettings(section, projectName='hanzilib'):
    """
    Reads the configuration from the given section of the project's config file.

    :type section: str
    :param section: section of the config file
    :type projectName: str
    :param projectName: name of project which will be used as name of the
        config file
    :rtype: dict
    :return: configuration settings for the given project
    """
    # don't convert to lowercase
    h = configparser.ConfigParser.optionxform
    try:
        configparser.ConfigParser.optionxform = lambda self, x: x
        config = configparser.ConfigParser()
        homeDir = os.path.expanduser('~')

        configFiles = []
        # Library directory
        # libdir = locateProjectFile(projectName)
        # if not libdir:
        #     if projectName != 'hanzilib':
        #         import warnings
        #         warnings.warn("Cannot locate packaged files for project '%s'"
        #             % projectName)
        #     # fall back to the directory of this file, only works for cjklib
        libdir = os.path.dirname(os.path.abspath(__file__))
        configFiles.append(os.path.join(libdir, '%s.conf' % projectName))

        # Windows
        if 'APPDATA' in os.environ:
            configFiles += [
                os.path.join(os.environ["APPDATA"], projectName,
                    '%s.conf' % projectName),
                ]
        # OSX
        if platform.system() == 'Darwin':
            configFiles += [
                os.path.join("/Library", "Application Support", projectName,
                    '%s.conf' % projectName),
                os.path.join(homeDir, "Library", "Application Support",
                    projectName, '%s.conf' % projectName),
                ]
        # Unix
        configFiles += [
            os.path.join('/', 'etc', '%s.conf' % projectName),
            os.path.join(homeDir, '.%s.conf' % projectName),
            os.path.join(homeDir, '%s.conf' % projectName),
            ]

        config.read(configFiles)

        configuration = dict(config.items(section))
    except configparser.NoSectionError:
        configuration = {}

    configparser.ConfigParser.optionxform = h

    return configuration

def getSearchPaths(projectName='hanzilib'):
    """
    Gets a list of search paths for the given project.

    :type projectName: str
    :param projectName: name of project
    :rtype: list
    :return: list of search paths
    """
    searchPath = [
        # personal directory
        os.path.join(os.path.expanduser('~'), '.%s' % projectName),
        os.path.join(os.path.expanduser('~'), '%s' % projectName),
        ]

    # Unix
    searchPath += [
        "/usr/local/share/%s/" % projectName,
        "/usr/share/%s/" % projectName,
        # for Maemo
        "/media/mmc1/%s/" % projectName,
        "/media/mmc2/%s/" % projectName,
        ]

    # Windows
    if 'APPDATA' in os.environ:
        searchPath += [os.path.join(os.environ['APPDATA'], projectName)]
        import sys
        major, minor = sys.version_info[0:2]
        searchPath.append("C:\Python%d%d\share\%s" % (major, minor, projectName))

    # OSX
    if platform.system() == 'Darwin':
        searchPath += [
            os.path.join(os.path.expanduser('~'), "Library",
                "Application Support", projectName),
            os.path.join("/Library", "Application Support", projectName),
            ]

    # Respect environment variable, e.g. CJKLIB_DB_PATH
    env = "%s_DB_PATH" % projectName.upper()

    if env in os.environ and os.environ[env].strip():
        searchPath += os.environ[env].strip().split(os.path.pathsep)

    # Library directory
    # libdir = locateProjectFile(projectName)
    # if not libdir:
    #     if projectName != 'hanzilib':
    #         import warnings
    #         warnings.warn("Cannot locate packaged files for project '%s'"
    #             % projectName)
    #     # fall back to the directory of this file, only works for cjklib
    libdir = os.path.dirname(os.path.abspath(__file__))

    searchPath.append(libdir)

    return searchPath

def getDataPath() -> str:
    """Gets the path to packaged data."""

    buildModule = __import__("hanzilib.build")
    buildModulePath = os.path.dirname(os.path.abspath(
        buildModule.__file__))
    dataDir = os.path.join(buildModulePath, 'data')

    return dataDir

#{ Unicode support enhancement

# define our own titlecase methods, as the Python implementation is currently
#   buggy (http://bugs.python.org/issue6412), see also
#   http://www.unicode.org/mail-arch/unicode-ml/y2009-m07/0066.html
_FIRST_NON_CASE_IGNORABLE = re.compile(r"(?u)([.˳｡￮₀ₒ]?\W*)(\w)(.*)$")
"""
Regular expression matching the first alphabetic character. Include GR neutral
tone forms.
"""
def titlecase(strng):
    """
    Returns the string (without "word borders") in titlecase.

    This function is not designed to work for multi-entity strings in general
    but rather for syllables with apostrophes (e.g. ``'Ch’ien1'``) and combining
    diacritics (e.g. ``'Hm\\u0300h'``). It additionally needs to support cases
    where a multi-entity string can derive from a single entity as in the case
    for *GR* (e.g. ``'Shern.me'`` for ``'Sherm'``).

    :type strng: str
    :param strng:  a string
    :rtype: str
    :return: the given string in titlecase

    .. todo::
        * Impl: While this function is only needed as long as Python doesn't
          ship with a proper title casing algorithm as defined by Unicode, we
          need a proper handling for *Wade-Giles*, as *Pinyin* *Erhua* forms
          will convert to two entities being separated by a hyphen, which does
          not fall in to the Unicode title casing algorithm's definition of a
          case-ignorable character.
    """
    matchObj = _FIRST_NON_CASE_IGNORABLE.match(strng.lower())
    if matchObj:
        tonal, firstChar, rest = matchObj.groups()
        return tonal + firstChar.upper() + rest

def istitlecase(strng):
    """
    Checks if the given string is in titlecase.

    :type strng: str
    :param strng:  a string
    :rtype: bool
    :return: ``True`` if the given string is in titlecase according to
        L{titlecase()}.
    """
    return titlecase(strng) == strng

# Helper methods

def cross_dict(*args: dict):
    """Builds a cross product of the given dicts."""
    return [{**{k: v for d in item for k, v in d.items()}} for item in itertools.product(*args)]

# Helper classes

class CharacterRangeIterator:
    """Iterates over a given set of codepoint ranges given in hex."""

    def __init__(self, ranges: list[tuple[str, str]]):
        self.ranges = ranges[:]
        self._curRange = self._popRange()

    def _popRange(self):
        if self.ranges:
            charRange = self.ranges[0]
            del self.ranges[0]
            if type(charRange) == type(()):
                rangeFrom, rangeTo = charRange
            else:
                rangeFrom, rangeTo = (charRange, charRange)
            return (int(rangeFrom, 16), int(rangeTo, 16))
        else:
            return []
        
    def __iter__(self):
        return self
    
    def __next__(self):
        if not self._curRange:
            raise StopIteration

        curIndex, toIndex = self._curRange
        if curIndex < toIndex:
            self._curRange = (curIndex + 1, toIndex)
        else:
            self._curRange = self._popRange()
        return chr(curIndex)

# Library extensions

class UnicodeCSVFileIterator(object):
    """Provides a CSV file iterator supporting Unicode."""
    class DefaultDialect(csv.Dialect):
        """Defines a default dialect for the case sniffing fails."""
        quoting = csv.QUOTE_NONE
        delimiter = ','
        lineterminator = '\n'
        quotechar = "'"
        # the following are needed for Python 2.4
        escapechar = "\\"
        doublequote = True
        skipinitialspace = False

    def __init__(self, fileHandle):
        self.fileHandle = fileHandle

    def __iter__(self):
        return self

    def __next__(self):
        if not hasattr(self, '_csvReader'):
            self._csvReader = self._getCSVReader(self.fileHandle)

        return [cell for cell in next(self._csvReader)]

    @staticmethod
    def utf_8_encoder(unicode_csv_data):
        for line in unicode_csv_data:
            yield line

    @staticmethod
    def byte_string_dialect(dialect):
        class ByteStringDialect(csv.Dialect):
            def __init__(self, dialect):
                for attr in ["delimiter", "quotechar", "escapechar",
                    "lineterminator"]:
                    old = getattr(dialect, attr)
                    if old is not None:
                        setattr(self, attr, str(old))

                for attr in ["doublequote", "skipinitialspace", "quoting"]:
                    setattr(self, attr, getattr(dialect, attr))

                csv.Dialect.__init__(self)

        return ByteStringDialect(dialect)

    def _getCSVReader(self, fileHandle):
        """
        Returns a csv reader object for a given file name.

        The file can start with the character '#' to mark comments. These will
        be ignored. The first line after the leading comments will be used to
        guess the csv file's format.

        :type fileHandle: file
        :param fileHandle: file handle of the CSV file
        :rtype: instance
        :return: CSV reader object returning one entry per line
        """
        def prependLineGenerator(line, data):
            """
            The first line red for guessing format has to be reinserted.
            """
            yield line
            for nextLine in data:
                yield nextLine

        line = '#'
        try:
            while line.strip().startswith('#'):
                line = next(fileHandle)
        except StopIteration:
            return csv.reader(fileHandle)
        try:
            self.fileDialect = csv.Sniffer().sniff(line, ['\t', ','])
            # fix for Python 2.4
            if len(self.fileDialect.delimiter) == 0:
                raise csv.Error()
        except csv.Error:
            self.fileDialect = UnicodeCSVFileIterator.DefaultDialect()

        content = prependLineGenerator(line, fileHandle)
        return csv.reader(
            UnicodeCSVFileIterator.utf_8_encoder(content),
            dialect=UnicodeCSVFileIterator.byte_string_dialect(
                self.fileDialect))
        #return csv.reader(content, dialect=self.fileDialect) # TODO


class ExtendedOption(Option):
    """
    Extends optparse by adding:

    - bool type, boolean can be set by ``True`` or ``False``, no one-way
      setting
    - path type, a list of paths given in one string separated by a colon
      ``':'``
    - extend action that resets a default value for user specified options
    - append action that resets a default value for user specified options
    """
    # taken from ConfigParser.RawConfigParser
    _boolean_states = {'1': True, 'yes': True, 'true': True, 'on': True,
                       '0': False, 'no': False, 'false': False, 'off': False}
    def check_bool(option, opt, value):
        if value.lower() in ExtendedOption._boolean_states:
            return ExtendedOption._boolean_states[value.lower()]
        else:
            raise OptionValueError(
                "option %s: invalid bool value: %r" % (opt, value))

    def check_pathstring(option, opt, value):
        if not value:
            return []
        else:
            return value.split(':')

    TYPES = Option.TYPES + ("bool", "pathstring")
    TYPE_CHECKER = copy.copy(Option.TYPE_CHECKER)
    TYPE_CHECKER["bool"] = check_bool
    TYPE_CHECKER["pathstring"] = check_pathstring

    ACTIONS = Option.ACTIONS + ("extendResetDefault", "appendResetDefault")
    STORE_ACTIONS = Option.STORE_ACTIONS + ("extendResetDefault",
        "appendResetDefault")
    TYPED_ACTIONS = Option.TYPED_ACTIONS + ("extendResetDefault",
        "appendResetDefault")
    ALWAYS_TYPED_ACTIONS = Option.ALWAYS_TYPED_ACTIONS + ("extendResetDefault",
        "appendResetDefault")

    def take_action(self, action, dest, opt, value, values, parser):
        if action == "extendResetDefault":
            if not hasattr(self, 'resetDefault'):
                self.resetDefault = set()
            if dest not in self.resetDefault:
                del values.ensure_value(dest, [])[:]
                self.resetDefault.add(dest)
            values.ensure_value(dest, []).extend(value)
        elif action == "appendResetDefault":
            if not hasattr(self, 'resetDefault'):
                self.resetDefault = set()
            if dest not in self.resetDefault:
                del values.ensure_value(dest, [])[:]
                self.resetDefault.add(dest)
            values.ensure_value(dest, []).append(value)
        else:
            Option.take_action(
                self, action, dest, opt, value, values, parser)

#{ SQLAlchemy column types

class _CollationMixin(object):
    def __init__(self, collation=None, **kwargs):
        """
        :param collation: Optional, a column-level collation for this string
          value.
        """
        self.collation = kwargs.get('collate', collation)

    def _extend(self, spec):
        """
        Extend a string-type declaration with standard SQL COLLATE annotation.
        """

        if self.collation:
            collation = 'COLLATE %s' % self.collation
        else:
            collation = None

        return ' '.join([c for c in (spec, collation) if c is not None])

    def get_search_list(self):
        return tuple()

class CollationString(_CollationMixin, String):
    def __init__(self, length=None, collation=None, **kwargs):
        """
        Construct a VARCHAR.

        :param collation: Optional, a column-level collation for this string
          value.
        """
        String.__init__(self, length)
        _CollationMixin.__init__(self, collation, **kwargs)

    def get_col_spec(self):
        if self.length:
            return self._extend("VARCHAR(%d)" % self.length)
        else:
            return self._extend("VARCHAR")


class CollationText(_CollationMixin, Text):
    def __init__(self, length=None, collation=None, **kwargs):
        """
        Construct a TEXT.

        :param collation: Optional, a column-level collation for this string
          value.
        """
        Text.__init__(self, length)
        _CollationMixin.__init__(self, collation, **kwargs)

    def get_col_spec(self):
        if self.length:
            return self._extend("TEXT(%d)" % self.length)
        else:
            return self._extend("TEXT")

# Decorators

import functools
class cachedmethod(object):
    """
    Decorate a method to memoize its return value. Only applicable for
    methods without arguments.
    """
    def __init__(self, fget):
        self.fget = fget
        self.__doc__ = fget.__doc__
        self.__name__ = fget.__name__

    def __get__(self, obj, cls):
        @functools.wraps(self.fget)
        def oneshot(*args, **kwargs):
            @functools.wraps(self.fget)
            def memo(*a, **k): return result
            result = self.fget(*args, **kwargs)
            # save to instance __dict__
            args[0].__dict__[self.__name__] = memo
            return result
        return oneshot.__get__(obj, cls)


import warnings
import functools

def deprecated(func):
    """
    Decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    """
    @functools.wraps(func)
    def new_func(*args, **kwargs):
        warnings.warn("Call to deprecated function %s." % func.__name__,
            category=DeprecationWarning, stacklevel=2)
        return func(*args, **kwargs)
    return new_func


class LazyDict[K, V](dict[K, V]):
    """A dict that will load entries on-demand."""
    def __init__(self, creator: Callable[[K], V], *args):
        dict.__init__(self, *args)
        self.creator = creator

    def __missing__(self, key: K):
        self[key] = value = self.creator(key)
        return value
