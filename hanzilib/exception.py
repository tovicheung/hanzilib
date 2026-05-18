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

"""
Error classes.
"""

class ConversionError(Exception):
    """
    A ConversionError is raised on a general conversion exception (e.g. no
    mapping).
    """

class AmbiguousConversionError(ConversionError):
    """
    An AmbiguousConversionError is raised when a conversion of one entity from
    one reading to another is ambiguous.
    """

class DecompositionError(Exception):
    """
    A DecompositionError is raised on a general decomposition exception (e.g.
    reading string has a bad format).
    """

class AmbiguousDecompositionError(DecompositionError):
    """
    An AmbiguousDecompositionError is raised when decomposition of a string
    written in a reading is ambiguous.
    """

class CompositionError(Exception):
    """
    A CompositionError is raised on a general composition exception (e.g.
    non-reading entities are rejected).
    """

class InvalidEntityError(DecompositionError):
    """
    An InvalidEntityError is raised when a entity given (e.g. through
    decomposition) is invalid for the current reading.
    """

class NoInformationError(Exception):
    """
    A NoInformationError is raised when the database lacks information for the
    given lookup value.
    """

class UnsupportedError(Exception):
    """
    An UnsupportedError is raised when the given option is not supported.
    """
