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
Entry factories for dictionaries.
"""

__all__ = [
    # entry factories
    "Tuple", "NamedTuple", "UnifiedHeadword",
    ]


from collections import namedtuple


#{ Entry factories

class Tuple(object):
    """Basic entry factory, returning a tuple of columns."""
    def getEntries(self, results):
        """
        Returns the dictionary results as lists.
        """
        return results


class NamedTuple(object):
    """
    Factory returning tuple entries with attribute-style access.
    """
    def _getNamedTuple(self):
        if not hasattr(self, '_namedTuple'):
            self._namedTuple = self._createNamedTuple('EntryTuple',
                self.columnNames)
        return self._namedTuple

    @staticmethod
    def _createNamedTuple(typename, fieldNames):
        return namedtuple(typename, fieldNames)

    def setDictionaryInstance(self, dictInstance):
        if not hasattr(dictInstance, 'COLUMNS'):
            raise ValueError('Incompatible dictionary')

        self.columnNames = dictInstance.COLUMNS

    def getEntries(self, results):
        """
        Returns the dictionary results as named tuples.
        """
        EntryTuple = self._getNamedTuple()
        return map(EntryTuple._make, results)


class UnifiedHeadword(NamedTuple):
    """
    Factory adding a simple *Headword* key for CEDICT style dictionaries to
    provide results compatible with EDICT. An alternative headword is given in
    brackets if two different headword instances are provided in the entry.
    """
    def __init__(self, headword='s'):
        NamedTuple.__init__(self)
        if headword in ('s', 't'):
            self.headword = headword
        else:
            raise ValueError("Invalid type for headword '%s'."
                % headword \
                + " Allowed values 's'implified or 't'raditional")

    def _unifyHeadwords(self, entry):
        entry = list(entry)
        if self.headword == 's':
            headwords = (entry[0], entry[1])
        else:
            headwords = (entry[1], entry[0])

        if headwords[0] == headwords[1]:
            entry.append(headwords[0])
        else:
            entry.append('%s（%s）' % headwords)
        return entry

    def getEntries(self, results):
        """
        Returns the dictionary results as named tuples.
        """
        def augmentedEntry(entry):
            entry = self._unifyHeadwords(entry)
            return EntryTuple._make(entry)

        EntryTuple = self._getNamedTuple()
        return map(augmentedEntry, results)

    def setDictionaryInstance(self, dictInstance):
        super(UnifiedHeadword, self).setDictionaryInstance(
            dictInstance)
        if not hasattr(dictInstance, 'COLUMNS'):
            raise ValueError('Incompatible dictionary')

        self.columnNames = dictInstance.COLUMNS + ['Headword']
